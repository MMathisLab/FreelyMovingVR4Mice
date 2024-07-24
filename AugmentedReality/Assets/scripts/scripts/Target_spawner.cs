using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.MLAgents;
//using UnityEngine.UIElements;
using UnityEngine.UI;

public class Target_spawner : MonoBehaviour
{
    public float targetsFromMidline = 1;
    public float targetsZpos = 3;
    public float targetsheight = 4;
    public float target_size = 1;
    public GameObject blue_target;
    public GameObject green_target;
    public float target_rotation = 0f;
    public GameObject Ri_wall;
    public GameObject Le_wall;
    public GameObject occluding_wall;
    public GameObject middle_occluding_wall;
    public float probGreenLeft;
    public float slitSize;
    public float hslitSize;
    public float slitDepth;
    public bool green_on_left;
    public GameObject bt;
    public GameObject gt;
    public Vector3 Lwall_pos;
    public Vector3 Rwall_pos; 
    public float wall_height;
    bool mouse_can_report;
    //IFloatProperties resetParams;
    public Renderer rend;
    public GameObject[] targets;
    public float target_selection = 0f;
    public float distractor_selection = 0f;
    public float occlusion_type = 0f;
    public float object_on_left;

  
   
    // Start is called before the first frame update
    void Start()
    {
        SetResetParams();
        targetSelection();
        if (occlusion_type == 1f){
            occlusion_slit();
        }
        if (occlusion_type == 2f){
            middle_occlusion();
        }
        //walls_reset();
    }


    void occlusion_slit(){
        hslitSize =  slitSize/2;
        Lwall_pos = new Vector3 (-5f - hslitSize,  wall_height, slitDepth/2);
        Rwall_pos = new Vector3 (+5f + hslitSize,  wall_height,  slitDepth/2);
        Le_wall = Instantiate(occluding_wall, Lwall_pos,transform.rotation* Quaternion.Euler (0f, 90f, 0f), this.transform.GetChild(0).transform);
        Le_wall.name = "Le_wall";
        Le_wall.transform.localScale += new Vector3(slitDepth-1f, 0f, 0f);
        
        Ri_wall = Instantiate(occluding_wall, Rwall_pos,transform.rotation* Quaternion.Euler (0f, 90f, 0f), this.transform.GetChild(0).transform);
        Ri_wall.name = "Ri_wall";
        Ri_wall.transform.localScale += new Vector3(slitDepth-1f, 0f, 0f);
    }
    public void walls_reset(){

        hslitSize =  slitSize/2;
        Destroy(Le_wall);
        Destroy(Ri_wall);
        occlusion_slit();
        //Ri_wall.transform.position.x = +5f + hslitSize;

    }

	void middle_occlusion()
	{
		Vector3 middle_wall_pos = new Vector3(0, wall_height, slitDepth / 2);
		GameObject M_wall = Instantiate(middle_occluding_wall, Lwall_pos, transform.rotation * Quaternion.Euler(0f, 90f, 0f), this.transform.GetChild(0).transform);
		M_wall.name = "M_wall";
		M_wall.transform.localScale += new Vector3(slitDepth - 1f, wall_height, slitSize);
	}

    void targetSpawnerGL()
    {
        bt =Instantiate(blue_target, new Vector3(+targetsFromMidline, targetsheight, targetsZpos), transform.rotation* Quaternion.Euler (90f, target_rotation, -90f));
        gt =Instantiate(green_target, new Vector3(-targetsFromMidline, targetsheight, targetsZpos), transform.rotation* Quaternion.Euler (90f, -target_rotation, 90f));
        
    }

    void setTag(){
        bt.tag = "Targets";
        gt.tag = "Targets";
        Ri_wall.tag ="Wall";
        Le_wall.tag ="Wall";
    }

     void targetSpawnerGL_1T()
    {
        
        gt =Instantiate(green_target, new Vector3(-targetsFromMidline, targetsheight, targetsZpos), transform.rotation* Quaternion.Euler (90f, -target_rotation, 90f));
        
    }

    void targetSpawnerGR()
    {
         bt = Instantiate(blue_target, new Vector3(-targetsFromMidline, targetsheight, targetsZpos), transform.rotation* Quaternion.Euler (90f, -target_rotation, 90f));
         gt = Instantiate(green_target, new Vector3(+targetsFromMidline, targetsheight, targetsZpos), transform.rotation* Quaternion.Euler (90f, +target_rotation, -90f));
    }

     void targetSpawnerGR_1T()
    {
         gt = Instantiate(green_target, new Vector3(+targetsFromMidline, targetsheight, targetsZpos), transform.rotation* Quaternion.Euler (90f, target_rotation, -90f));
    }


	public void Spawn_distractor()
	{
		SetResetParams();
		if (object_on_left == 1.0f)
		{
			Debug.Log("object on left");
			targetSpawnerGL();
			green_on_left = true;
		}
		else
		{
			targetSpawnerGR();
			green_on_left = false;
			Debug.Log("object on right");
		}
		gt.transform.localScale = new Vector3(target_size, target_size, target_size);
		bt.transform.localScale = new Vector3(target_size, target_size, target_size);

		bt.name = "blue_target";
		gt.name = "green_target";
	}

	public void Spawn()
	{
		SetResetParams();
		if (object_on_left == 1.0f)
		{
			targetSpawnerGL_1T();
			green_on_left = true;
		}
		else
		{
			targetSpawnerGR_1T();
			green_on_left = false;
		}
		gt.transform.localScale = new Vector3(target_size, target_size, target_size);

		gt.name = "green_target";
	}

	public void targetSelection()
	{
		green_target = targets[(int)target_selection];
		blue_target = targets[(int)distractor_selection];
	}

    public void DestroyTargets(){
    
    GameObject [] targets = GameObject.FindGameObjectsWithTag ("Targets");
    for(var i = 0 ; i < targets.Length ; i ++)
     {
         Destroy(targets[i]);
     }
    

    }

	public void Targets_set_visable()
	{

		GameObject[] targets = GameObject.FindGameObjectsWithTag("Targets");
		for (var i = 0; i < targets.Length; i++)
		{
			rend = targets[i].GetComponent<Renderer>();
			rend.enabled = true;
		}
	}



	void SetResetParams()
	{

		var environmentParameters = Academy.Instance.EnvironmentParameters;

		targetsheight = environmentParameters.GetWithDefault("targetsHeight", 3);
		targetsZpos = environmentParameters.GetWithDefault("targetDistance", 3);
		target_size = environmentParameters.GetWithDefault("targetSize", 2);
		targetsFromMidline = environmentParameters.GetWithDefault("targetsFromMidline", 4f);
		slitSize = environmentParameters.GetWithDefault("slitSize", 4.9f);
		slitDepth = environmentParameters.GetWithDefault("slit_depth", 0.01f);
		object_on_left = environmentParameters.GetWithDefault("Object_on_Left", 0.0f);
		wall_height = environmentParameters.GetWithDefault("wall_height", 2f);
		target_selection = environmentParameters.GetWithDefault("target_selection", 6f);
		distractor_selection = environmentParameters.GetWithDefault("distractor_selection", 4f);
		occlusion_type = environmentParameters.GetWithDefault("occlusion_type", 1f);
		targetsZpos = environmentParameters.GetWithDefault("targetsZpos", 3f);

	}

}

