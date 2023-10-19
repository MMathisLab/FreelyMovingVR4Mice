using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using MLAgents;
//using UnityEngine.UIElements;
using UnityEngine.UI;

public class CameraSelect : MonoBehaviour
{
    IFloatProperties resetParams;
    public float CameraSelection;
    public Camera offAxisCamera;
    public Camera onAxisCamera;
    // Start is called before the first frame update
    void Start()
    {
        SetResetParams();
        if (CameraSelection == 0f){
            Debug.Log("using on axis camera");
            offAxisCamera.enabled = false;
            onAxisCamera.enabled = true;
        }
        if (CameraSelection == 1f){
            Debug.Log("using off axis camera");
            offAxisCamera.enabled = true;
            onAxisCamera.enabled = false;
        }
        
    }

    void SetResetParams(){
        resetParams = Academy.Instance.FloatProperties;
        CameraSelection =resetParams.GetPropertyWithDefault("cameraSelection", 0f);
   
   }
}
