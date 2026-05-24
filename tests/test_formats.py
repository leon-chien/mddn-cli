from pathlib import Path

import numpy as np
import MDAnalysis as mda
from mddatanet.convert import convert_package
from mddatanet.features.compute import featurize_package
from mddatanet.format.validation import validate_package

def create_tiny_gro_xtc(prefix: Path):
    gro_path = prefix / "tiny.gro"
    xtc_path = prefix / "tiny.xtc"
    
    # Create a universe with 10 atoms
    n_atoms = 10
    n_frames = 5
    resnames = ["ALA"] * n_atoms
    names = ["CA"] * n_atoms
    u = mda.Universe.empty(n_atoms, n_residues=n_atoms, atom_resindex=np.arange(n_atoms), trajectory=True)
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resids", np.arange(n_atoms) + 1)
    
    # Set some positions and box
    u.atoms.positions = np.random.random((n_atoms, 3)).astype(np.float32) * 10
    u.dimensions = [20, 20, 20, 90, 90, 90]
    
    # Write GRO
    u.atoms.write(str(gro_path))
    
    # Write XTC
    with mda.Writer(str(xtc_path), n_atoms) as W:
        for _i in range(n_frames):
            u.atoms.positions += np.random.random((n_atoms, 3)).astype(np.float32)
            W.write(u)
            
    return gro_path, xtc_path

def test_convert_gro_xtc(tmp_path):
    gro, xtc = create_tiny_gro_xtc(tmp_path)
    out = tmp_path / "test.mddatanet"
    
    convert_package(
        topology=gro,
        trajectory=xtc,
        coordinates=None,
        name="test_gro_xtc",
        out=out,
        overwrite=True
    )
    
    result = validate_package(out)
    assert result.ok
    
    # Test featurize on this package
    feature_config = {
        "features": [
            {
                "name": "dist",
                "type": "distance",
                "selection_a": "index 0",
                "selection_b": "index 1"
            }
        ]
    }
    feat_out = tmp_path / "test_feat.mddatanet"
    featurize_package(
        input_path=out,
        out=feat_out,
        feature_config=feature_config,
        overwrite=True
    )
    
    result = validate_package(feat_out)
    assert result.ok

def create_tiny_pdb_dcd(prefix: Path):
    pdb_path = prefix / "tiny.pdb"
    dcd_path = prefix / "tiny.dcd"
    
    n_atoms = 5
    n_frames = 3
    u = mda.Universe.empty(n_atoms, n_residues=1, atom_resindex=[0]*n_atoms, trajectory=True)
    u.add_TopologyAttr("names", ["N", "CA", "C", "O", "CB"])
    u.add_TopologyAttr("resnames", ["ALA"])
    u.atoms.positions = np.random.random((n_atoms, 3)).astype(np.float32) * 5
    
    u.atoms.write(str(pdb_path))
    
    with mda.Writer(str(dcd_path), n_atoms) as W:
        for _i in range(n_frames):
            u.atoms.positions += np.random.random((n_atoms, 3)).astype(np.float32)
            W.write(u)
            
    return pdb_path, dcd_path

def test_convert_pdb_dcd(tmp_path):
    pdb, dcd = create_tiny_pdb_dcd(tmp_path)
    out = tmp_path / "test_pdb_dcd.mddatanet"
    
    convert_package(
        topology=pdb,
        trajectory=dcd,
        coordinates=None,
        name="test_pdb_dcd",
        out=out,
        overwrite=True
    )
    
    result = validate_package(out)
    assert result.ok
