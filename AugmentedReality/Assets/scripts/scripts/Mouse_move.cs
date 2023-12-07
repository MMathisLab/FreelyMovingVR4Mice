using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using MLAgents;
//using UnityEngine.UIElements;
using UnityEngine.UI;


public class Mouse_move : Agent
{
    // Start is called before the first frame update
  
  Rigidbody rBody;
  public GameObject plane;
  float totalEpisodeTime;
  public float maxEpisodeTime =10;
  public float ITI_length = 2;
  bool ITI = false;
  public GameObject[] ITI_screen;
  public float ITIGreyScreen = 0f;
  public bool mouse_can_report = false;
  private float inITItimer; 
  public bool ITI_timed = false;
  public bool mouse_report_correct = false;
  public float mouseReportDelay;
  public bool mouseInLeft_box = false;
  public bool mouseInRight_box =false;

  public float box_delay = 0.25f;
  public float report_box_delay = 0.1f;
  public float velocity_threshold = 0.5f;
  public float L_box_delay = 0f;
  public float R_box_delay = 0f;
  public float start_box_delay= 0f;

  public float L_box_x_min;
  public float L_box_x_max;
  public float L_box_z_min;
  public float L_box_z_max;

  public float R_box_x_min;
  public float R_box_x_max;
  public float R_box_z_min;
  public float R_box_z_max;

  public float TT_box_x_min;
  public float TT_box_x_max;
  public float TT_box_z_min;
  public float TT_box_z_max;
  public float TT_box_angle;
  public Vector3 prevPos = new Vector3(0f,0f,0f);
  public float speed;
  public float distractor;
  public bool targets_visable = false;
  public Image sync;
  

  IFloatProperties resetParams;
  
 

    // Start is called before the first frame update
  void Start()
    {
        SetResetParams();
        plane.GetComponent<Target_spawner>().DestroyTargets();
        rBody = GetComponent<Rigidbody>();
        ITIScreenOff();
    }

    public override void AgentReset()
    {
      SetResetParams();
      
      plane.GetComponent<Target_spawner>().DestroyTargets();
      mouse_can_report = false;
      float spawned = 0f;
      targets_visable = false;
      
      if (distractor == 0.0f) {
        Debug.Log("no distractor");
         plane.GetComponent<Target_spawner>().Spawn();
         spawned = 1f;
      }
      if (distractor == 1.0f) {
         Debug.Log("distractor");
         plane.GetComponent<Target_spawner>().Spawn_distractor();
         spawned = 1f;
      }
      
      
      
      totalEpisodeTime = 0;
      
      start_box_delay = 0f;
      L_box_delay = 0f;
      R_box_delay =0f;

      ITIScreenOff();
      ITI = false;
      


      
      //this.transform.position = new Vector3(0, 0.5f, -6);
    }

    private void ITIScreenOff() {
        foreach (GameObject can in ITI_screen)
        {
         // Debug.Log(can);
          can.SetActive(false);

        }
    }

    private void ITIScreenOn() {
        //Debug.Log("turn on");
        foreach (GameObject can in ITI_screen)
        {
            can.SetActive(true);

        }
    }


    public override void AgentAction(float[] vectorAction)
    {
      float thisReward = 0;
      totalEpisodeTime += Time.deltaTime;
        
        //move the Mouse, to x y and head angle of actual mouse 
        if (targets_visable == false){
          plane.GetComponent<Target_spawner>().Targets_set_visable();
          targets_visable = true;
        }
        
        float x = vectorAction[0];
        float z = vectorAction[1];
        float head_angle = vectorAction[2];
        
        this.transform.position = new Vector3(x, 0.5f, z);
        this.transform.eulerAngles = new Vector3(0.0f, head_angle, 0.0f);
        Vector3 currVel = (this.transform.position - prevPos) / Time.deltaTime;
        speed = currVel.magnitude;
        prevPos = this.transform.position;
        //Debug.Log(speed);
        mouseInRight_box = agentInBox(R_box_x_min, R_box_x_max, R_box_z_min, R_box_z_max, false);
        
        mouseInLeft_box = agentInBox(L_box_x_min, L_box_x_max, L_box_z_min, L_box_z_max, false);
        
        if (mouse_can_report) {
          //Debug.Log("mouse can report");
          MouseReported();
          if (mouse_report_correct == true) {
              //Debug.Log("mouse report correct");
              
              thisReward =1f;
              mouse_report_correct = false;
              mouse_can_report = false;
              Debug.Log("rewarded");
              
              
          }
              
        }
        
        //EpisdoeTimeOut();
        mouse_can_report_trigger();

        // Trigger ITI either - ITI can be timed or next episode can start when the agent looks back at the screen in a frontal box
        
        triggerGreyScreen_agentTriggerd();

        
       
      SetReward(thisReward);
      //Debug.Log(thisReward);

    }


    public override void CollectObservations()
    {
      // log agent position and heading direction
      AddVectorObs(this.transform.position.x);
      AddVectorObs(this.transform.position.z);
      AddVectorObs(this.transform.eulerAngles.y);
      AddVectorObs(mouse_can_report);
      AddVectorObs(ITI);
      AddVectorObs(plane.GetComponent<Target_spawner>().green_on_left);
      AddVectorObs(mouse_report_correct);
      AddVectorObs(mouseInLeft_box);
      AddVectorObs(mouseInRight_box);
      AddVectorObs(speed);
      AddVectorObs(sync.GetComponent<PhotodiodeChange>().sync_state);
    }

    public override float[] Heuristic()
    {
        var action = new float[3];
        action[0] = this.transform.position.x;
        action[1] = this.transform.position.z;
        action[2] = this.transform.eulerAngles.y;
        return action;
    }


    /* void EpisdoeTimeOut(){
      if ((totalEpisodeTime > maxEpisodeTime) & (ITI != true)){
        ITI = true;
        inITItimer = 0;
      }
    } */
    /* 
    void triggerGreyScreenTimed()
    {
      if (ITI == true){
        inITItimer += Time.deltaTime;
      
        if (inITItimer < ITI_length) {
          ITI_screen.SetActive(true);
        }
        else {
          Done();
        }
      }
      if(ITI == false){
        ITI_screen.SetActive(false); 
      }  
      
    } */

     void triggerGreyScreen_agentTriggerd()
     {
      if (ITI == true){
        //Debug.Log("ITI_triggered");
        //Debug.Log("ITI_triggered by agent triggered function");
        inITItimer += Time.deltaTime;
        if (ITIGreyScreen == 1f) {
            Debug.Log("grey screen");
           ITIScreenOn();
        }
        
        bool inbox = agentInBox(TT_box_x_min, TT_box_x_max, TT_box_z_min, TT_box_z_max, true);
        if (inbox == true) 
        {
          if (speed < velocity_threshold){
            //Debug.Log(speed);
            start_box_delay += Time.deltaTime;
            if (start_box_delay > box_delay){
             Done();
             ITI = false;
            
            }
          }
        }
        else {
          start_box_delay = 0f;
        }
      }
     
      
    }

    bool agentInBox(float xmin, float xmax, float zmin, float zmax,  bool atScreen) 
    {
      if ((this.transform.position.x > xmin) & (this.transform.position.x < xmax) & (this.transform.position.z > zmin) & (this.transform.position.z < zmax)) 
      {
        if (atScreen){
          if ((transform.eulerAngles.z >= 0 && this.transform.eulerAngles.y <= TT_box_angle) || (this.transform.eulerAngles.y >= (360-TT_box_angle) && this.transform.eulerAngles.y <= 360f))
          {
            return true;
          }
          else 
          {
            return false;
          }
          }
          else 
          {
            return true;
          }
      }
      
      
      else 
      {
        return false;
      }
    }

    void mouse_can_report_trigger()
    {
      if ((totalEpisodeTime > mouseReportDelay) & (!ITI)) {
        mouse_can_report = true;
      }
      else {
        mouse_can_report = false;
      }

    }

    void MouseReported()
      {
        if (mouseInLeft_box) {
            //Debug.Log("mouse in left box");
            L_box_delay += Time.deltaTime;
          }
        else
        {
          L_box_delay = 0f;
        }
        
        if (mouseInRight_box) {
            //Debug.Log("mouse in right box");
            R_box_delay += Time.deltaTime;
          }
        else
        {
          R_box_delay = 0f;
        }

        if ((L_box_delay > report_box_delay) | (R_box_delay > report_box_delay))
        {
          
          if (((plane.GetComponent<Target_spawner>().green_on_left == true) & (mouseInLeft_box == true)) | ((plane.GetComponent<Target_spawner>().green_on_left == false) & (mouseInRight_box == true))){
            mouse_report_correct = true;
            plane.GetComponent<Target_spawner>().DestroyTargets();
            mouse_can_report = false;
            ITI = true;

          }
          else {
            mouse_report_correct = false;
            plane.GetComponent<Target_spawner>().DestroyTargets();
            mouse_can_report = false;
            ITI = true;

          }
        }
        
    }
    

    void SetResetParams(){
    resetParams = Academy.Instance.FloatProperties;
    mouseReportDelay = resetParams.GetPropertyWithDefault("mouseReportDelay", 5f);
    start_box_delay = resetParams.GetPropertyWithDefault("startBoxDelay", 0.25f);
    velocity_threshold = resetParams.GetPropertyWithDefault("velocityThreshold", 0.5f);
    report_box_delay = resetParams.GetPropertyWithDefault("reportBoxDelay", 0.1f);
    distractor = resetParams.GetPropertyWithDefault("distractor", 1.0f);
    L_box_x_min = resetParams.GetPropertyWithDefault("L_box_x_min", -10f);
    L_box_x_max = resetParams.GetPropertyWithDefault("L_box_x_max", -6f);
    L_box_z_min = resetParams.GetPropertyWithDefault("L_box_z_min", -10f);
    L_box_z_max = resetParams.GetPropertyWithDefault("L_box_z_max", 0f);

    R_box_x_min = resetParams.GetPropertyWithDefault("R_box_x_min", 6f);
    R_box_x_max = resetParams.GetPropertyWithDefault("R_box_x_max", 10f);
    R_box_z_min = resetParams.GetPropertyWithDefault("R_box_z_min", -10f);
    R_box_z_max = resetParams.GetPropertyWithDefault("R_box_z_max", 0f);

    TT_box_x_min = resetParams.GetPropertyWithDefault("TT_box_x_min", -4f);
    TT_box_x_max = resetParams.GetPropertyWithDefault("TT_box_x_max", 4f);
    TT_box_z_min = resetParams.GetPropertyWithDefault("TT_box_z_min", -5f);
    TT_box_z_max = resetParams.GetPropertyWithDefault("TT_box_z_max", 0f);
    TT_box_angle = resetParams.GetPropertyWithDefault("TT_box_angle", 90f);

    ITIGreyScreen = resetParams.GetPropertyWithDefault("Grey_screen_active", 0f);

   }


    
 }

