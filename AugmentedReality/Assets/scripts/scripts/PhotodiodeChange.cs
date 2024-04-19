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
		float grayscale = ChangeColor();
		sync_state = grayscale;
	}

	private float ChangeColor()
	{
		// squareImage.color = squareImage.color == blackColor ? whiteColor : blackColor;
		float grayscale = mouse_agent.photodiode_change_value;
		Color color = new Color(grayscale, grayscale, grayscale);
		squareImage.color = color;
		return grayscale;
	}
}
