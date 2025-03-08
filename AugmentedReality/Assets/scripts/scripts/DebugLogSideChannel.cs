using Unity.MLAgents.SideChannels;
using UnityEngine;

public class DebugLogSideChannel : SideChannel
{
	public DebugLogSideChannel()
	{
		// Assign a unique UUID for this side channel
		ChannelId = new System.Guid("6146928a-ea90-4477-b497-c2f10400de1b");
	}

	protected override void OnMessageReceived(IncomingMessage msg)
	{
		// This side channel is for sending logs out, so no incoming messages are expected
	}

	public void SendLog(string logMessage, string stackTrace, LogType type)
	{
		using (var msg = new OutgoingMessage())
		{
			msg.WriteString(logMessage);
			QueueMessageToSend(msg);
		}
	}
}
