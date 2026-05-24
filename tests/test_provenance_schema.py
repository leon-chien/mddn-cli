from mddatanet.format.schema import Provenance, SourceFile


def test_provenance_schema_valid():
    provenance = Provenance(source_files=[SourceFile(path="traj.xtc", sha256="abc")])

    assert provenance.created_by == "mddatanet"
    assert provenance.source_files[0].path == "traj.xtc"

