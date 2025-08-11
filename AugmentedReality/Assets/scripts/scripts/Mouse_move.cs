using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.MLAgents;
using Unity.MLAgents.Sensors;
using Unity.MLAgents.Actuators;
//using UnityEngine.UIElements;
using UnityEngine.UI;
using System.Diagnostics;
using System;


public class Mouse_move : Agent
{
	// Start is called before the first frame update

	Rigidbody rBody;
	public GameObject plane;
	float totalEpisodeTime;
	public float maxEpisodeTime = 10;
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
	public bool mouseInRight_box = false;

	public float box_delay = 0.25f;
	public float report_box_delay = 0.1f;
	public float velocity_threshold = 0.5f;
	public float L_box_delay = 0f;
	public float R_box_delay = 0f;
	public float start_box_delay = 0f;

	public float L_box_x_min;
	public float L_box_x_max;
	public float L_box_z_min;
	public float L_box_z_max;

	public float R_box_x_min;
	public float R_box_x_max;
	public float R_box_z_min;
	public float R_box_z_max;
	public Camera offaxis;
	public float TT_box_x_min;
	public float TT_box_x_max;
	public float TT_box_z_min;
	public float TT_box_z_max;
	public float TT_box_angle;
	public Vector3 prevPos = new Vector3(0f, 0f, 0f);

	[Tooltip("Maximum units per second agent can move")]
	public float maxMoveSpeed = 5f;
	[Tooltip("Maximum degrees per second agent can rotate")]
	public float maxRotationSpeed = 90f;

	float start_x;
	float start_z;
	float start_angle;
	public float speed;
	public float distractor;
	public bool targets_visable = false;

	public float photodiode_change_value;
	public Image sync;
	Stopwatch stopwatch;
	float lastFrameTime;


	// Start is called before the first frame update
	void Start()
	{
		SetResetParams();
		plane.GetComponent<Target_spawner>().DestroyTargets();
		rBody = GetComponent<Rigidbody>();
		ITIScreenOff();

		stopwatch = new Stopwatch();
		stopwatch.Start();
		lastFrameTime = (float)stopwatch.Elapsed.TotalSeconds;
	}

	public override void OnEpisodeBegin()
	{
		SetResetParams();

		// Resetting agent position to default
		transform.position = new Vector3(start_x, 0.5f, start_z);
		transform.eulerAngles = new Vector3(0.0f, start_angle, 0.0f);

		rBody.velocity = Vector3.zero;
		rBody.angularVelocity = Vector3.zero;

		plane.GetComponent<Target_spawner>().DestroyTargets();
		mouse_can_report = false;
		float spawned = 0f;
		targets_visable = false;

		if (distractor == 0.0f)
		{
			plane.GetComponent<Target_spawner>().Spawn();
			spawned = 1f;
		}
		if (distractor == 1.0f)
		{
			plane.GetComponent<Target_spawner>().Spawn_distractor();
			spawned = 1f;
		}

		totalEpisodeTime = 0;

		start_box_delay = 0f;
		L_box_delay = 0f;
		R_box_delay = 0f;

		ITIScreenOff();
		ITI = false;

		if (plane.GetComponent<Target_spawner>().occlusion_type > 0f)
		{
			plane.GetComponent<Target_spawner>().walls_reset();
		}

		stopwatch.Restart();
		lastFrameTime = (float)stopwatch.Elapsed.TotalSeconds;
	}

	float GetDeltaTime()
	{
		// float currentTime = (float)stopwatch.Elapsed.TotalSeconds;
		// float deltaTime = currentTime - lastFrameTime;
		// lastFrameTime = currentTime;
		// return deltaTime;
		return Time.fixedDeltaTime;
	}

	private void ITIScreenOff()
	{
		foreach (GameObject can in ITI_screen)
		{
			can.SetActive(false);
		}
	}

	private void ITIScreenOn()
	{
		foreach (GameObject can in ITI_screen)
		{
			can.SetActive(true);

		}
	}


	public override void OnActionReceived(ActionBuffers actions)
	{
		float thisReward = 0;
		float deltaTime = GetDeltaTime();
		totalEpisodeTime += deltaTime;

		//move the Mouse, to x y and head angle of actual mouse 
		if (targets_visable == false)
		{
			plane.GetComponent<Target_spawner>().Targets_set_visable();
			targets_visable = true;
		}

		// 1) Read raw actions
		float dx = actions.ContinuousActions[0];
		float dz = actions.ContinuousActions[1];
		float da = actions.ContinuousActions[2];
		photodiode_change_value = actions.ContinuousActions[3];

		UnityEngine.Debug.Log($"[DEBUG] Position before action: {transform.position.x}, {transform.position.z}, {transform.eulerAngles.y}");
		UnityEngine.Debug.Log($"[DEBUG] Action received dx: {dx}, dz: {dz}, da: {da}");
		UnityEngine.Debug.Log($"[DEBUG] Delta time computed: {deltaTime}");

		// 2) Incremental head rotation (do this first)
		float deltaHead = da * maxRotationSpeed * deltaTime;
		Quaternion targetRot = Quaternion.Euler(0f, transform.eulerAngles.y + deltaHead, 0f);
		rBody.MoveRotation(targetRot);

		// 3) Compute movement delta & apply (after rotation)
		Vector3 step = new Vector3(dx, 0f, dz) * maxMoveSpeed * deltaTime;
		Vector3 newPos = transform.position + step;
		newPos.x = Mathf.Clamp(newPos.x, -9f, 9f);
		newPos.z = Mathf.Clamp(newPos.z, -10f, -2f);
		rBody.MovePosition(newPos);

		// 4) Compute speed for observations
		Vector3 currVel = (newPos - prevPos) / deltaTime;

		speed = currVel.magnitude;
		prevPos = newPos;

		mouseInRight_box = agentInBox(R_box_x_min, R_box_x_max, R_box_z_min, R_box_z_max, false);
		mouseInLeft_box = agentInBox(L_box_x_min, L_box_x_max, L_box_z_min, L_box_z_max, false);

		if (mouse_can_report)
		{
			MouseReported(deltaTime);
			if (mouse_report_correct == true)
			{
				thisReward = 1f;
				mouse_report_correct = false;
				mouse_can_report = false;
			}

		}

		//EpisdoeTimeOut();
		mouse_can_report_trigger();

		// Trigger ITI either - ITI can be timed or next episode can start when the agent looks back at the screen in a frontal box
		triggerGreyScreen_agentTriggerd(deltaTime);

		SetReward(thisReward);
	}


	public override void CollectObservations(VectorSensor sensor)
	{
		// log agent position and heading direction
		sensor.AddObservation(this.transform.position.x);  // 0
		sensor.AddObservation(this.transform.position.z); // 1
		sensor.AddObservation(this.transform.eulerAngles.y); // 2
		sensor.AddObservation(mouse_can_report); // 3
		sensor.AddObservation(ITI); // 4
		sensor.AddObservation(plane.GetComponent<Target_spawner>().green_on_left); // 5
		sensor.AddObservation(mouse_report_correct); // 6
		sensor.AddObservation(mouseInLeft_box); // 7
		sensor.AddObservation(mouseInRight_box); // 8
		sensor.AddObservation(speed); // 9
		sensor.AddObservation(sync.GetComponent<PhotodiodeChange>().sync_state);// 10
		sensor.AddObservation(photodiode_change_value); //11
		sensor.AddObservation(start_box_delay); // 12
	}

	public override void Heuristic(in ActionBuffers actionsOut)
	{
		var continuousActionsOut = actionsOut.ContinuousActions;

		// 1) Head: Horizontal axis → turn left/right
		//    Raw in [-1,1], zero means "no turn"
		float rawHead = Input.GetAxis("Horizontal");
		continuousActionsOut[2] = rawHead;

		// 2) Movement: Vertical axis → forward/back, relative to current heading
		//    Raw in [-1,1], zero means "no move"
		float moveInput = Input.GetAxis("Vertical");
		float yawRad = transform.eulerAngles.y * Mathf.Deg2Rad;
		float rawX = Mathf.Sin(yawRad) * moveInput;
		float rawZ = Mathf.Cos(yawRad) * moveInput;
		continuousActionsOut[0] = rawX;
		continuousActionsOut[1] = rawZ;

		// 3) Photodiode: keep at zero unless you want manual control
		continuousActionsOut[3] = 0f;
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

	void triggerGreyScreen_agentTriggerd(float deltaTime)
	{
		if (ITI == true)
		{
			inITItimer += deltaTime;
			if (ITIGreyScreen == 1f)
			{
				ITIScreenOn();
			}

			bool inbox = agentInBox(TT_box_x_min, TT_box_x_max, TT_box_z_min, TT_box_z_max, true);
			if (inbox == true)
			{
				if (speed < velocity_threshold)
				{
					start_box_delay += deltaTime;
					if (start_box_delay > box_delay)
					{
						EndEpisode();
						ITI = false;

					}
				}
			}
			else
			{
				start_box_delay = 0f;
			}
		}


	}

	bool agentInBox(float xmin, float xmax, float zmin, float zmax, bool atScreen)
	{
		if ((this.transform.position.x > xmin) & (this.transform.position.x < xmax) & (this.transform.position.z > zmin) & (this.transform.position.z < zmax))
		{
			if (atScreen)
			{
				if ((transform.eulerAngles.y >= 0 && this.transform.eulerAngles.y <= TT_box_angle) || (this.transform.eulerAngles.y >= (360 - TT_box_angle) && this.transform.eulerAngles.y <= 360f))
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
		if ((totalEpisodeTime > mouseReportDelay) & (!ITI))
		{
			mouse_can_report = true;
		}
		else
		{
			mouse_can_report = false;
		}

	}

	void MouseReported(float deltaTime)
	{
		if (mouseInLeft_box)
		{
			L_box_delay += deltaTime;
		}
		else
		{
			L_box_delay = 0f;
		}

		if (mouseInRight_box)
		{
			R_box_delay += deltaTime;
		}
		else
		{
			R_box_delay = 0f;
		}

		if ((L_box_delay > report_box_delay) | (R_box_delay > report_box_delay))
		{

			if (((plane.GetComponent<Target_spawner>().green_on_left == true) & (mouseInLeft_box == true)) | ((plane.GetComponent<Target_spawner>().green_on_left == false) & (mouseInRight_box == true)))
			{
				mouse_report_correct = true;
				plane.GetComponent<Target_spawner>().DestroyTargets();
				mouse_can_report = false;
				ITI = true;

			}
			else
			{
				mouse_report_correct = false;
				plane.GetComponent<Target_spawner>().DestroyTargets();
				mouse_can_report = false;
				ITI = true;

			}
		}

	}


	void SetResetParams()
	{

		UnityEngine.Debug.Log($"[DEBUG] Resetting environment...");
		var environmentParameters = Academy.Instance.EnvironmentParameters;

		mouseReportDelay = environmentParameters.GetWithDefault("mouseReportDelay", 5f);
		box_delay = environmentParameters.GetWithDefault("startBoxDelay", 0.25f);
		velocity_threshold = environmentParameters.GetWithDefault("velocityThreshold", 0.5f);
		report_box_delay = environmentParameters.GetWithDefault("reportBoxDelay", 0.1f);
		distractor = environmentParameters.GetWithDefault("distractor", 1.0f);
		L_box_x_min = environmentParameters.GetWithDefault("L_box_x_min", -10f);
		L_box_x_max = environmentParameters.GetWithDefault("L_box_x_max", -6f);
		L_box_z_min = environmentParameters.GetWithDefault("L_box_z_min", -10f);
		L_box_z_max = environmentParameters.GetWithDefault("L_box_z_max", 0f);

		R_box_x_min = environmentParameters.GetWithDefault("R_box_x_min", 6f);
		R_box_x_max = environmentParameters.GetWithDefault("R_box_x_max", 10f);
		R_box_z_min = environmentParameters.GetWithDefault("R_box_z_min", -10f);
		R_box_z_max = environmentParameters.GetWithDefault("R_box_z_max", 0f);

		TT_box_x_min = environmentParameters.GetWithDefault("TT_box_x_min", -4f);
		TT_box_x_max = environmentParameters.GetWithDefault("TT_box_x_max", 4f);
		TT_box_z_min = environmentParameters.GetWithDefault("TT_box_z_min", -5f);
		TT_box_z_max = environmentParameters.GetWithDefault("TT_box_z_max", 0f);
		TT_box_angle = environmentParameters.GetWithDefault("TT_box_angle", 90f);

		ITIGreyScreen = environmentParameters.GetWithDefault("Grey_screen_active", 0f);

		start_x = environmentParameters.GetWithDefault("start_x", 0f);
		start_z = environmentParameters.GetWithDefault("start_z", -8f);
		start_angle = environmentParameters.GetWithDefault("start_angle", 0f);
	}
}

