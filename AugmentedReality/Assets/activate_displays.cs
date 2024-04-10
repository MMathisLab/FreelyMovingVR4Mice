using UnityEngine;
using System.Collections;
using JetBrains.Annotations;
using UnityEngine.UI;


public class activate_displays : MonoBehaviour
{
    public GameObject main_camera; 
    public Canvas photodiode;
    
    void Start ()
    {

        Debug.Log ("displays connected: " + Display.displays.Length);
            // Display.displays[0] is the primary, default display and is always ON, so start at index 1.
            // Check if additional displays are available and activate each.
        if (Display.displays.Length > 1) 
        {
            for (int i = 1; i < Display.displays.Length; i++)
            {
                Display.displays[i].Activate();
            }
            
        }
        else
        {
          main_camera.GetComponent<Camera>().targetDisplay = 0;  
          photodiode.targetDisplay = 0;
          //Debug.Log(main_camera.GetComponent<Camera>().enabled);
          //Display.displays[0].Activate();
        }
       
    }
}