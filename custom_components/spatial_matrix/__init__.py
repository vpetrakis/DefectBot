import streamlit.components.v1 as components
import os

# Find the compiled React build folder
_RELEASE = True
if _RELEASE:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _spatial_matrix = components.declare_component("spatial_matrix", path=build_dir)
else:
    # Used for local development hot-reloading
    _spatial_matrix = components.declare_component("spatial_matrix", url="http://localhost:3001")

# The function you will call in app.py
def spatial_risk_matrix(data_json, key=None):
    # This sends data to React, and waits for React to send data back
    component_value = _spatial_matrix(data=data_json, key=key, default=None)
    return component_value

