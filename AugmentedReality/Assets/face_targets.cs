using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class face_targets : MonoBehaviour

{   
    public GameObject mouse;
    Vector3 target;
    // Start is called before the first frame update
    void Start()
    {
        target = new Vector3(0f,2f,6f);
    }

    // Update is called once per frame
    void Update()
    {
       // transform.rotation = Quaternion.Euler(new Vector3(-4f, 0f, 0f));
       this.transform.position =  mouse.transform.position;
       
       transform.LookAt(target);
    }
}
