using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class OffAxisMoveWithMouse : MonoBehaviour
{
    public GameObject mouse;
    // Start is called before the first frame update
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        this.transform.position = new Vector3(mouse.transform.position.x, this.transform.position.y, mouse.transform.position.z);
        
    }
}
