import os
import streamlit.components.v1 as components

# This physically locates the compiled React code folder
parent_dir = os.path.dirname(os.path.abspath(__file__))
build_dir = os.path.join(parent_dir, "frontend/build")
_spatial_matrix = components.declare_component("spatial_matrix", path=build_dir)

def spatial_risk_matrix(data_json, key=None):
    """Sends JSON to React, returns user interaction back to Python."""
    return _spatial_matrix(data=data_json, key=key, default=None)
