import { Streamlit, withStreamlitConnection, ComponentProps } from "streamlit-component-lib"
import React, { useEffect } from "react"
import "./SpatialMatrix.css"

const SpatialMatrix = (props: ComponentProps) => {
  const data = props.args.data || []

  useEffect(() => {
    // Dynamically scale height to avoid scrollbars inside the iframe
    Streamlit.setFrameHeight(Math.max(600, Math.ceil(data.length / 3) * 150))
  }, [data.length])

  const onNodeClicked = (vessel: string, caseRef: string) => {
    // Send 60fps interaction back to Python server instantly
    Streamlit.setComponentValue({ action: "inspect", vessel: vessel, ref: caseRef })
  }

  return (
    <div className="matrix-container">
      {data.map((item: any) => {
        let borderClass = "node-monitor"
        if (item.Recommendation === "CRITICAL THREAT") borderClass = "node-critical"
        if (item.Recommendation === "DISP REQUIRED") borderClass = "node-review"

        return (
          <div 
            key={item.id} 
            className={`matrix-node ${borderClass}`}
            onClick={() => onNodeClicked(item.Vessel, item['Case Ref'])}
          >
            <div className="node-vessel">{item.Vessel} // {item['Case Ref']}</div>
            <div className="node-risk">Risk: {item['Risk Score']}</div>
            <div className="node-desc">${item['Expected Loss'].toLocaleString()} | {item.Description}</div>
          </div>
        )
      })}
    </div>
  )
}

export default withStreamlitConnection(SpatialMatrix)

export default withStreamlitConnection(SpatialMatrix)
