# Experiments

The following list presents the main experiments performed during the project in chronological order:

| # | ID   | Algo | Arch | Obs. Space (3 channels RGB) | Task type | Mean Ep. Rew. | Mean Ep. Len. | Reward Shaping (correct, wrong, step) | Notes |
|:---:|:-----:|:-----:|:-----:|:----:|:----------:|:-------:|:----:|:----------:|:-----:|
|1|_20250820_2211|PPO | pre-trained MobileNetV3 + value_net[64], policy_net[64]|256x512|shape discrim (with occluders)|-0.1638|16.38 steps|+1.5, 0, -0.01|didn't learn|
|2|_20250821_1022|PPO|same|256x512|shape discrim (with occluders)|-0.2217|23|+1.5, 0, -0.01|didn't learn|
|3|_20250821_1033|PPO|same|256x512|shape discrim (with occluders)|-0.2591|25.91|+1.5, 0, -0.01|didn't learn|
|4|_20250821_1549|PPO|same|256x512|shape discrim (with occluders)|-0.091145|182.29|+1, -1, -.0005|didn't learn|
|5|_20250821_1551|PPO|same|256x512|shape discrim (with occluders)|N/A|N/A|+1, -0, -.0005|didn't learn|
|6|_20250821_1553|PPO|same|256x512|shape discrim (with occluders)|-0.04286|85.72|+0, -1, -.0005|didn't learn|
|7|_20250822_1158|PPO|same|256x512|detection (no occluders)|-0.089|89|+1, -1, -.001|didn't learn|
|8|_20250822_1159|PPO|same|256x512|color discrimination (no occluders)|-0.012750002|32.77|+1, -1, -.001|didn't learn|
|9|_20250822_1201|PPO|same|256x512|shape discrimination (no occluders)|-0.0825|82.5|+1, -1, -.001|didn't learn|
|10|_20250822_1327|PPO|same|256x512|detection (no occluders)|-0.3777|43.8|+2, -2, -.01|learned but noisy trajectories|
|11|_20250822_1328|PPO|same|256x512|color discrimination (no occluders)|-0.98249996|98.25|+2, -2, -.01|learned but noisy trajectories|
|12|_20250822_1330|PPO|same|256x512|shape discrimination (no occluders)|-0.8422|82.23|+2, -2, -.01|just goes to right port|
|13|_20250822_1942|PPO|same|256x512|shape discrimination (no occluders)|-0.197|25.73|+2, -2, -.01|removed ability to move backwards, led to easier training|
|⚠️|-|-|-|-|-|-|-|-|-|
|14|_20250825_1517|PPO|pre-trained MobileNetV3 + value_net[512,256], policy_net[256,128]|225x400|color discrimination (no occluders)|1.1709|63.81|+2, -2, -0.01|similar performance as previous exp.|
|15|_20250825_1956|RecurrentPPO|pre-trained MobileNetV3 + LSTM[256] (not shared) + value_net[512,256], policy_net[256,128]|225x400|color discrimination (no occluders)|0.67475|100.08|+2, -2, -0.015|x|
|16|_20250825_1959|RecurrentPPO|pre-trained MobileNetV3 + LSTM[256,256] (not shared) + value_net[512,256], policy_net[256,128]|225x400|color discrimination (no occluders)|0.82285|65|+2, -2, -0.015|x|
|17|_20250826_1332|PPO|pre-trained MobileNetV3 + value_net[512,512,512], policy_net[256,256,256]|225x400|color discrimination (no occluders)|0.4806|65.9|+2, -2, -0.02|x|
|18|_20250827_1021|PPO|untrained NatureCNN (sb3 default) + value_net[512,256,128,512,256,128], policy_net[512,256,128,512,256,128]|225x400|color discrimination (no occluders)|1.0326|47.74|+1.5, -1.5, -0.01|x|
|19|_20250827_1624|PPO|untrained CustomExtractor (bigger version of the 3-layer NatureCNN) + value_net[512,256,128], policy_net[512,256,128]|225x400|color discrimination (no occluders)|0.9425|53.73|+1.5, -1.5, -0.01|x|
|20|_20250828_1536|RecurrentPPO|untrained NatureCNN + LSTM[256] (not shared) + value_net[256,256,128], policy_net[256,256,128]|225x400|shape discrimination (no occluders)|0.7592003|64.57|+1.5, -1.5, -0.01|normalizes both observations and rewards|
|21|_20250830_1320|RecurrentPPO|untrained 4-layer CNN with GroupNorm and final GAP + LSTM[256] (not shared) + value_net[256,256,256], policy_net[256,256,256]|225x400|shape discrimination (no occluders)|1.0325003|47.75|+1.5, -1.5, -0.01|removes reward normalization but keeps obs. norm.|
|22|_20250831_1051|RecurrentPPO|untrained 4-layer CNN with GroupNorm and final GAP + LSTM[200] (not shared) + value_net[512,384,256], policy_net[512,384,256]|225x400|shape discrimination (no occluders)|1.1247002|38.53|+1.5, -1.5, -0.01|x|
|23|_20250901_1143|RecurrentPPO|untrained 4-layer CNN with GroupNorm and 3-layer MLP + LSTM[100] (not sharde) + value_net[384,256], policy_net[384,256]|225x400|shape discrimination (no occluders)|1.5|37.45|+1.5, -1.5, -1.5 (time-out penalty), -0 (step penalty)|fast learning and good performance|
|24|_20250901_1426|RecurrentPPO|DepthWiseExtractor with 3-layer MLP + LSTM[200] (not shared) + value_net[400,300,200], policy_net[400,300,200]|225x400|shape discrimination (no occluders)|1.5|51.65|same|best performance so far|
|25|_20250901_1722|RecurrentPPO|DepthWiseExtractor with 3-layer MLP + LSTM[200] (not shared) + value_net[400,300,200], policy_net[400,300,200]|225x400|shape discrimination (with occluders)|1.35|61.25|same|best performance so far. This model is `_20250901_1426` but "finetuned" on task with occluders (i.e. Curriculum Learning)|

⚠️ <b>Major change</b>:
- Randomized starting position and starting head angle (in [-45, +45] deg).
- Reduced input observation size from 256x512 to 225x400.
- Fixed reward assignment. No longer handled by Unity but by the RL task wrapper directly.
    - Has impact on computed `mean episode reward` values after the change. Before this changes, values are not truly representative of the model's performance.

**NOTE: for any run listed above, except for `_20250821_1551`, a corresponding configuration file can be found within the `rl_task/EXPERIMENTS/` folder for further information about the training parameters used.**

## Best configurations [currently]

### PPO

```
config = dict(
    seed=None,
    env_name="AugmentedReality",
    algorithm="PPO",
    # environment
    env_kwargs=dict(
        task_config="shape_discrim",
        pos_reward_size=1.5,
        neg_reward_size=1.5,
        trunc_penalty_size=1.5,
        step_penalty_size=0.0,
        max_episode_steps=220,
    ),
    # rollout / optimization
    algo_kwargs=dict(
        policy="CnnPolicy",
        learning_rate=1e-4,
        n_steps=256,
        batch_size=192,
        n_epochs=4,
        gamma=0.99,
        gae_lambda=0.97,
        clip_range=0.2,
        ent_coef=0.005,
        vf_coef=0.5,
        max_grad_norm=0.5,
        target_kl=None,
        use_sde=False,
    ),
    # model / policy
    policy_kwargs=dict(
        net_arch=dict(pi=[256, 128], vf=[256, 128]),
        activation_fn=torch.nn.SiLU,
        normalize_images=True,  # SB3 scales to [0,1]
    ),
    # training budget
    num_envs=6,
    total_timesteps=1_000_000,
)
```

### RecurrentPPO

```
config = dict(
    seed=None,
    env_name="AugmentedReality",
    algorithm="RecurrentPPO",
    # environment
    env_kwargs=dict(
        task_config="shape_discrim_multi_occluders",
        pos_reward_size=1.5,
        neg_reward_size=1.5,
        trunc_penalty_size=1.5,
        step_penalty_size=0.0,
        max_episode_steps=220,
    ),
    # rollout / optimization
    algo_kwargs=dict(
        policy="CnnLstmPolicy",
        learning_rate=3e-5,
        n_steps=256,
        batch_size=96,
        n_epochs=3,
        gamma=0.99,
        gae_lambda=0.97,
        clip_range=0.15,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
        target_kl=0.03,
        use_sde=False,
    ),
    # policy
    policy_kwargs=dict(
        optimizer_class=torch.optim.Adam,
        features_extractor_class=DepthwiseExtractor,
        share_features_extractor=True,
        features_extractor_kwargs=dict(
            features_dim=400,
            base_channels=24,
            use_depthwise=True,
            pool_out=(12, 8),
            head_channels=32,
            mlp_hidden=(1024, 512),
        ),
        net_arch=dict(
            pi=[400, 300, 200],
            vf=[400, 300, 200],
        ),
        activation_fn=torch.nn.SiLU,
        ortho_init=True,
        lstm_hidden_size=200,
        n_lstm_layers=1,
        shared_lstm=False,
        enable_critic_lstm=True,
        normalize_images=True,  # SB3 input images to [0,1]
    ),
    # training budget
    num_envs=8,
    total_timesteps=5_000_000,
)
```