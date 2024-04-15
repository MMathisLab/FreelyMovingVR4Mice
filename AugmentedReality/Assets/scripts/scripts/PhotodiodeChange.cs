using UnityEngine;
using UnityEngine.UI;

public class PhotodiodeChange : MonoBehaviour
{
	private Image squareImage;
	private Color blackColor = Color.black;
	private Color whiteColor = Color.white;
	public float sync_state = 0;
	public Mouse_move mouse_agent;

	private void Start()
	{
		squareImage = GetComponent<Image>();
	}

	private void FixedUpdate()
	{
		ChangeColor();
		if (squareImage.color == Color.black)
		{
			sync_state = 1f;
		}
		else
		{
			sync_state = 2f;
		}
	}

	private void ChangeColor()
	{
		// squareImage.color = squareImage.color == blackColor ? whiteColor : blackColor;
		float grayscale = mouse_agent.photodiode_change_value;
		Color color = new Color(grayscale, grayscale, grayscale);
		squareImage.color = color;
	}
}
