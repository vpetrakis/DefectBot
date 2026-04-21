import { Streamlit, withStreamlitConnection, ComponentProps } from "streamlit-component-lib"
import React, { useEffect } from "react"
// Imagine importing Three.js or a fluid Drag-and-Drop library here

const SpatialMatrix = (props: ComponentProps) => {
  // 1. Receive data from your Python Pandas dataframe
  const fleetData = props.args["data"]

  // 2. Tell Streamlit how tall this component should be
  useEffect(() => {
    Streamlit.setFrameHeight(600)
  }, [])

  // 3. A function that triggers when a user interacts at 60fps
  const onVesselClicked = (vesselName: string) => {
    // SEND DATA BACK TO PYTHON instantly
    Streamlit.setComponentValue({ action: "inspect", target: vesselName })
  }

  // 4. Render the hyper-smooth UI (React handles this, not Streamlit)
  return (
    <div className="cinematic-react-container">
       {/* Your custom 3D WebGL canvas or fluid drag-and-drop 
         interface goes here, completely immune to Streamlit's lag.
       */}
       <button onClick={() => onVesselClicked(fleetData[0].vessel)}>
         Inspect {fleetData[0].vessel}
       </button>
    </div>
  )
}

export default withStreamlitConnection(SpatialMatrix)
