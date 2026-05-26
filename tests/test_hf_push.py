from unittest.mock import patch

from mddatanet.hf.workspace import (
    dataset_card,
    init_workspace,
    package_workspace,
    prepare_workspace,
    publish_workspace,
)

from tests.helpers import write_ligand_unbinding_pdb


def _packaged_project(tmp_path):
    pdb = write_ligand_unbinding_pdb(tmp_path / "tiny.pdb")
    project = tmp_path / "project"
    init_workspace(project)
    prepare_workspace(project_root=project, topology=pdb, keep_solvent=True, overwrite=True)
    package_workspace(project_root=project, hf_repo_link="mddatanet/tiny")
    return project


def test_publish_dry_run_materializes_hf_repo_files(tmp_path):
    project = _packaged_project(tmp_path)
    out = tmp_path / "upload"

    publish_workspace(project_root=project, repo_id="mddatanet/tiny", dry_run_out=out)

    assert (out / "README.md").exists()
    assert (out / "data" / "train-00000-of-00001.parquet").exists()
    assert (out / "metadata_index" / "index-00000-of-00001.parquet").exists()
    assert "task_categories" in (out / "README.md").read_text(encoding="utf-8")


def test_publish_calls_hf_api(tmp_path):
    project = _packaged_project(tmp_path)

    with patch("huggingface_hub.HfApi") as api_cls:
        publish_workspace(project_root=project, repo_id="user/tiny", private=True, token="token")

    api = api_cls.return_value
    api.create_repo.assert_called_once()
    _, create_kwargs = api.create_repo.call_args
    assert create_kwargs["repo_id"] == "user/tiny"
    assert create_kwargs["private"] is True
    assert api.upload_folder.call_count == 2
    api.upload_file.assert_called_once()


def test_dataset_card_has_hf_front_matter(tmp_path):
    project = _packaged_project(tmp_path)

    card = dataset_card(project, repo_id="mddatanet/tiny")

    assert card.startswith("---\n")
    assert "task_categories:" in card
    assert "- molecular-dynamics" in card
