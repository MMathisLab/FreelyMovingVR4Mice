# Experiments

The following list presents the main experiments performed during the project in chronological order:

| ID   | Algo | Arch | Obs. Space (3 channels RGB) | Task type | Mean Ep. Rew. | Mean Ep. Len. | Reward Shaping (correct, wrong, step) | Notes |
|:-----:|:-----:|:-----:|:----:|:----------:|:-------:|:----:|:----------:|:-----:|
| 20250820_2211|PPO | pre-trained MobileNetV3 + value_net[64], policy_net[64]|256x512|shape discrim (with occluders)|-0.1638|16.38 steps|+1.5, 0, -0.01|n_steps=2048|
|20250821_1022|PPO|same|256x512|shape discrim (with occluders)|-0.2217|23|+1.5, 0, -0.01|n_steps=1024|
|20250821_1033|PPO|same|256x512|shape discrim (with occluders)|-0.2591|25.91|+1.5, 0, -0.01|n_step=4096|
|20250821_1549|PPO|same|256x512|shape discrim (with occluders)|-0.091145|182.29|+1, -1, -.0005| didn't learn|
|20250821_1551|PPO|same|256x512|shape discrim (with occluders)|N/A|N/A|+1, -0, -.0005| didn't learn|
|20250821_1553|PPO|same|256x512|shape discrim (with occluders)|-0.04286|85.72|+0, -1, -.0005| didn't learn|
|20250822_1158|PPO|same|256x512|detection (no occluders)|-0.089|89|+1, -1, -.001|didn't learn|
|20250822_1159|PPO|same|256x512|color discrimination (no occluders)|-0.012750002|32.77|+1, -1, -.001|didn't learn|
|20250822_1201|PPO|same|256x512|shape discrimination (no occluders)|-0.0825|82.5|+1, -1, -.001|didn't learn|
|20250822_1327|PPO|same|256x512|detection (no occluders)|-0.3777|43.8|+2, -2, -.01|learned but noisy trajectories|
|20250822_1328|PPO|same|256x512|color discrimination (no occluders)|-0.98249996|98.25|+2, -2, -.01|learned but noisy trajectories|
|20250822_1330|PPO|same|256x512|shape discrimination (no occluders)|-0.8422|82.23|+2, -2, -.01|just goes to right port|
|20250822_1942|PPO|same|256x512|shape discrimination (no occluders)|-0.197|25.73|+2, -2, -.01|removed ability to move backwards, led to easier training|
|⚠️|⚠️|⚠️|⚠️|⚠️|⚠️|⚠️|⚠️|⚠️|
|20250825_1517|PPO|pre-trained MobileNetV3 + value_net[512,256], policy_net[256,128]|225x400|color discrimination (no occluders)|1.1709|63.81|+2, -2, -0.01|similar performance as previous exp.|
|20250825_1956|RecurrentPPO|pre-trained MobileNetV3 + LSTM[256] (not shared) + value_net[512,256], policy_net[256,128]|225x400|color discrimination (no occluders)|0.67475|100.08|+2, -2, -0.015|x|
|20250825_1959|RecurrentPPO|pre-trained MobileNetV3 + LSTM[256,256] (not shared) + value_net[512,256], policy_net[256,128]|225x400|color discrimination (no occluders)|0.82285|65|+2, -2, -0.015|x|
|20250826_1332|PPO|pre-trained MobileNetV3 + value_net[512,512,512], policy_net[256,256,256]|225x400|color discrimination (no occluders)|0.4806|65.9|+2, -2, -0.02|x|
|20250827_1021|PPO|untrained NatureCNN (sb3 default) + value_net[512,256,128,512,256,128], policy_net[512,256,128,512,256,128]|225x400|color discrimination (no occluders)|1.0326|47.74|+1.5, -1.5, -0.01|x|
|20250827_1624|PPO|untrained CustomExtractor (bigger version of the 3-layer NatureCNN) + value_net[512,256,128], policy_net[512,256,128]|225x400|color discrimination (no occluders)|0.9425|53.73|+1.5, -1.5, -0.01|x|
|20250828_1536|RecurrentPPO|untrained NatureCNN + LSTM[256] (not shared) + value_net[256,256,128], policy_net[256,256,128]|225x400|shape discrimination (no occluders)|0.7592003|64.57|+1.5, -1.5, -0.01|normalizes both observations and rewards|
|20250830_1320|RecurrentPPO|untrained 4-layer CNN with GroupNorm and final GAP + LSTM[256] (not shared) + value_net[256,256,256], policy_net[256,256,256]|225x400|shape discrimination (no occluders)|1.0325003|47.75|+1.5, -1.5, -0.01|removes reward normalization but keeps obs. norm.|
|20250830_1320|RecurrentPPO|untrained 4-layer CNN with GroupNorm and final GAP + LSTM[200] (not shared) + value_net[512,384,256], policy_net[512,384,256]|225x400|shape discrimination (no occluders)|1.1247002|38.53|+1.5, -1.5, -0.01|x|
|20250901_1143|RecurrentPPO|untrained 4-layer CNN with GroupNorm and 3-layer MLP + LSTM[100] (not sharde) + value_net[384,256], policy_net[384,256]|225x400|shape discrimination (no occluders)|1.5|37.45|+1.5, -1.5, -1.5 (time-out penalty), -0 (step penalty)|fast learning and good performance|
|20250901_1426|RecurrentPPO|DepthWiseExtractor with 3-layer MLP + LSTM[200] (not shared) + value_net[400,300,200], policy_net[400,300,200]|225x400|shape discrimination (no occluders)|1.5|51.65|same|best performance so far|
|20250901_1722|RecurrentPPO|DepthWiseExtractor with 3-layer MLP + LSTM[200] (not shared) + value_net[400,300,200], policy_net[400,300,200]|225x400|shape discrimination (with occluders)|1.35|61.25|same|best performance so far|

⚠️ <b>Major change</b>:
- Randomized starting position and starting head angle (in [-45, +45] deg).
- Reduced input observation size from 256x512 to 225x400.
- Fixed reward assignment. No longer handled by Unity but by the RL task wrapper directly.
    - Has impact on computed `mean episode reward` values after the change. Before this changes, values are not truly representative of the model's performance.
