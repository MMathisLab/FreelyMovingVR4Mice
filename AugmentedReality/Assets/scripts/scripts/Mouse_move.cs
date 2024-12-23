using UnityEngine;
using Unity.MLAgents;
using Unity.MLAgents.Sensors;
using Unity.MLAgents.Actuators;
using UnityEngine.UI;
using System.Diagnostics;


public class Mouse_move : Agent
{
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
	public float speed;
	public float distractor;
	public bool targets_visable = false;

	public float photodiode_change_value;
	public Image sync;
	Stopwatch stopwatch;
	float lastFrameTime;

	private bool rl_training = false; // Default value

	// Start is called before the first frame update
	void Start()
	{
		SetResetParams();


		// - - - - - retrieving RL  training param - - - - -
		var envParams = Academy.Instance.EnvironmentParameters;

		// Retrieve the "rl_training" parameter and set its value
		float rlTrainingValue = envParams.GetWithDefault("rl_training", 0.0f); // Default to 0.0 (-> False)
		UnityEngine.Debug.Log($"isTrainingValue: {rlTrainingValue}");
		rl_training = rlTrainingValue > 0.5f; // Convert float to bool

		UnityEngine.Debug.Log($"RL Training: {rl_training}");
		// - - - - - - - - - - - - - - - - - - - - - - - - - 


		plane.GetComponent<Target_spawner>().DestroyTargets();
		rBody = GetComponent<Rigidbody>();
		ITIScreenOff();
		stopwatch = new Stopwatch();
		stopwatch.Start();
		lastFrameTime = (float)stopwatch.Elapsed.TotalSeconds;

		UnityEngine.Debug.Log("START");
		if (rl_training)
		{
			this.transform.position = new Vector3(0, 0.5f, -4.99f);
		}
	}

	public override void OnEpisodeBegin()
	{
		SetResetParams();

		plane.GetComponent<Target_spawner>().DestroyTargets();
		mouse_can_report = false;
		float spawned = 0f;
		targets_visable = false;

		if (distractor == 0.0f)
		{
			UnityEngine.Debug.Log("no distractor");
			plane.GetComponent<Target_spawner>().Spawn();
			spawned = 1f;
		}
		if (distractor == 1.0f)
		{
			UnityEngine.Debug.Log("distractor");
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
		float currentTime = (float)stopwatch.Elapsed.TotalSeconds;
		float deltaTime = currentTime - lastFrameTime;
		lastFrameTime = currentTime;
		return deltaTime;
	}

	private void ITIScreenOff()
	{
		foreach (GameObject can in ITI_screen)
		{
			// UnityEngine.Debug.Log(can);
			can.SetActive(false);

		}
	}

	private void ITIScreenOn()
	{
		//UnityEngine.Debug.Log("turn on");
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


		if (rl_training)
		{
			float x = this.transform.position.x + actions.ContinuousActions[0];
			float z = this.transform.position.z + actions.ContinuousActions[1];
			float head_angle = this.transform.eulerAngles.y + actions.ContinuousActions[2];
			photodiode_change_value = 1f;

			if (x < 9f & x > -9f & z < -2f & z > -10f)
			{
				this.transform.position = new Vector3(x, 0.5f, z);
			}
			this.transform.eulerAngles = new Vector3(0.0f, head_angle, 0.0f);
		}
		else
		{
			float x = actions.ContinuousActions[0];
			float z = actions.ContinuousActions[1];
			float head_angle = actions.ContinuousActions[2];
			photodiode_change_value = actions.ContinuousActions[3];

			this.transform.position = new Vector3(x, 0.5f, z);
			this.transform.eulerAngles = new Vector3(0.0f, head_angle, 0.0f);
		}

		Vector3 currVel = (this.transform.position - prevPos) / deltaTime;
		speed = currVel.magnitude;

		// update previous position to current to compute velocity at next iteration
		prevPos = this.transform.position;
		//UnityEngine.Debug.Log(speed);

		mouseInRight_box = agentInBox(R_box_x_min, R_box_x_max, R_box_z_min, R_box_z_max, false);

		mouseInLeft_box = agentInBox(L_box_x_min, L_box_x_max, L_box_z_min, L_box_z_max, false);

		if (mouse_can_report)
		{
			//UnityEngine.Debug.Log("mouse can report");
			MouseReported(deltaTime);
			if (mouse_report_correct)
			{
				//UnityEngine.Debug.Log("mouse report correct");

				thisReward = 1f;
				mouse_report_correct = false;
				mouse_can_report = false;
				UnityEngine.Debug.Log("rewarded");
			}
		}

		//EpisdoeTimeOut();
		mouse_can_report_trigger();

		// Trigger ITI either - ITI can be timed or next episode can start when the agent looks back at the screen in a frontal box
		triggerGreyScreen_agentTriggerd(deltaTime);

		SetReward(thisReward);
		//UnityEngine.Debug.Log(thisReward);

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
		ActionSegment<float> continuousActionsOut = actionsOut.ContinuousActions;

		continuousActionsOut[2] = 0f;

		float newPosition_x = this.transform.position.x + Input.GetAxis("Horizontal");
		float newPosition_z = this.transform.position.z + Input.GetAxis("Vertical");

		// need to stay within arena boundaries (same as python scripts)
		if (newPosition_x < 9f & newPosition_x > -9f & newPosition_z < -2f & newPosition_z > -10f)
		{
			// move
			continuousActionsOut[0] = newPosition_x;
			continuousActionsOut[1] = newPosition_z;
		}
		else
		{
			// keep current position
			continuousActionsOut[0] = this.transform.position.x;
			continuousActionsOut[1] = this.transform.position.z;
		}
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
			//UnityEngine.Debug.Log("ITI_triggered");
			//UnityEngine.Debug.Log("ITI_triggered by agent triggered function");
			inITItimer += deltaTime;
			if (ITIGreyScreen == 1f)
			{
				UnityEngine.Debug.Log("grey screen");
				ITIScreenOn();
			}

			bool inbox = agentInBox(TT_box_x_min, TT_box_x_max, TT_box_z_min, TT_box_z_max, true);
			if (inbox == true)
			{
				if (speed < velocity_threshold)
				{
					//UnityEngine.Debug.Log(speed);
					start_box_delay += deltaTime;
					//UnityEngine.Debug.Log(deltaTime);
					//UnityEngine.Debug.Log("delta_time");
					//UnityEngine.Debug.Log(Time.deltaTime);
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
			//UnityEngine.Debug.Log("mouse in left box");
			L_box_delay += deltaTime;
		}
		else
		{
			L_box_delay = 0f;
		}

		if (mouseInRight_box)
		{
			//UnityEngine.Debug.Log("mouse in right box");
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

				if (rl_training)
				{
					// resetting agent position to start (in TT box)
					this.transform.position = new Vector3(0, 0.5f, -4.99f);
					UnityEngine.Debug.Log("CORRECT! -- resetting artificial agent's position...");
				}
			}
			else
			{
				mouse_report_correct = false;
				plane.GetComponent<Target_spawner>().DestroyTargets();
				mouse_can_report = false;
				ITI = true;

				if (rl_training)
				{
					// resetting agent position to start (in TT box)
					this.transform.position = new Vector3(0, 0.5f, -4.99f);
					UnityEngine.Debug.Log("WRONG! -- resetting artificial agent's position...");
				}
			}
		}

	}


	void SetResetParams()
	{

		// resetParams = Academy.Instance.FloatProperties;
		var environmentParameters = Academy.Instance.EnvironmentParameters;

		mouseReportDelay = environmentParameters.GetWithDefault("mouseReportDelay", 5f); // original
		box_delay = environmentParameters.GetWithDefault("startBoxDelay", 0.25f); // original
		velocity_threshold = environmentParameters.GetWithDefault("velocityThreshold", 0.5f); // original

		// adjusting game parameters when training artificial agents on the task
		if (rl_training)
		{
			mouseReportDelay = environmentParameters.GetWithDefault("mouseReportDelay", 0.0f); // custom for RL training
			box_delay = environmentParameters.GetWithDefault("startBoxDelay", 0.01f); // custom for RL training
			velocity_threshold = environmentParameters.GetWithDefault("velocityThreshold", 100f); // custom for RL training

			UnityEngine.Debug.Log("--> Set RL environment training parameters <--");
		}

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

	}



}

