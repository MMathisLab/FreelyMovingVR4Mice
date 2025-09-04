"""Custom visual feature extractors for Stable-Baselines3 policies.

Includes:
- CustomExtractor: simple 3-layer CNN + 3-layer MLP producing features_dim.
- VanillaExtractor: deeper CNN with GroupNorm and MLP head.
- DepthwiseExtractor: depthwise-separable CNN stem + adaptive pool + MLP.
"""

from typing import Type, List, Optional, Dict, Sequence

import torch as th
import torch.nn as nn
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


def _ortho_init(m: nn.Module, gain: float = 1.0):
    if isinstance(m, (nn.Conv2d, nn.Linear)):
        nn.init.orthogonal_(m.weight, float(gain))
        if m.bias is not None:
            nn.init.constant_(m.bias, 0.0)


class CustomExtractor(BaseFeaturesExtractor):
    """3-layer CNN followed by a 3-layer MLP to features_dim.

    Validates provided layer sizes and initializes weights orthogonally.
    """

    def __init__(
        self,
        observation_space: spaces.Box,
        cnn_layers: List[int],
        cnn_activation_fn: str,
        mlp_layers: List[int],
        mlp_activation_fn: str,
        features_dim: int = 128,
    ):
        super().__init__(observation_space, features_dim=features_dim)

        if not isinstance(cnn_layers, list):
            raise TypeError("cnn_layers must be a list of 3 integers")
        if len(cnn_layers) != 3:
            raise ValueError("cnn_layers must contain exactly 3 integers")
        if not all(isinstance(x, int) for x in cnn_layers):
            raise TypeError("All elements in cnn_layers must be integers")

        if not isinstance(mlp_layers, list):
            raise TypeError("mlp_layers must be a list of 3 integers")
        if len(mlp_layers) != 3:
            raise ValueError("mlp_layers must contain exactly 3 integers")
        if not all(isinstance(x, int) for x in mlp_layers):
            raise TypeError("All elements in mlp_layers must be integers")

        C, H, W = observation_space.shape

        # --- CNN backbone ---
        layer1, layer2, layer3 = cnn_layers
        self.cnn = nn.Sequential(
            nn.Conv2d(C, layer1, kernel_size=5, stride=2, padding=0),
            cnn_activation_fn(),
            nn.Conv2d(layer1, layer2, kernel_size=3, stride=2, padding=0),
            cnn_activation_fn(),
            nn.Conv2d(layer2, layer3, kernel_size=3, stride=1, padding=0),
            cnn_activation_fn(),
            nn.Flatten(),
        )
        self.cnn_gain = _calc_gain(cnn_activation_fn)
        self.cnn.apply(lambda m: _ortho_init(m, gain=self.cnn_gain))

        # Probe CNN output dim
        with th.no_grad():
            dummy = th.zeros(1, C, H, W, dtype=th.float32)
            cnn_out_dim = self.cnn(dummy).shape[1]

        # --- MLP head ---
        layer1, layer2, layer3 = mlp_layers
        self.mlp = nn.Sequential(
            nn.Linear(cnn_out_dim, layer1),
            mlp_activation_fn(),
            nn.Linear(layer1, layer2),
            mlp_activation_fn(),
            nn.Linear(layer2, layer3),
            mlp_activation_fn(),
            nn.Linear(layer3, features_dim),
        )
        self.mlp_gain = _calc_gain(mlp_activation_fn)
        self.mlp.apply(lambda m: _ortho_init(m, gain=self.mlp_gain))

        self._features_dim = features_dim

    @property
    def features_dim(self) -> int:
        return self._features_dim

    def forward(self, observations: th.Tensor) -> th.Tensor:
        x = self.cnn(observations)
        x = self.mlp(x)
        return x


def _calc_gain(act_cls: Type[nn.Module], act_kwargs: Optional[Dict] = None) -> float:
    name = act_cls.__name__.lower()
    if name == "relu":
        return nn.init.calculate_gain("relu")
    if name == "leakyrelu":
        slope = (act_kwargs or {}).get("negative_slope", 0.01)
        return nn.init.calculate_gain("leaky_relu", param=slope)
    if name == "tanh":
        return nn.init.calculate_gain("tanh")  # 5/3
    if name == "sigmoid":
        return nn.init.calculate_gain("sigmoid")  # 1.0
    return 1.0  # safe default


def _gn_groups(C: int) -> int:
    for g in (32, 16, 8, 4, 2, 1):
        if C % g == 0:
            return g
    return 1


class VanillaExtractor(BaseFeaturesExtractor):
    def __init__(
        self,
        observation_space: spaces.Box,
        out_dim: int = 1024,
        use_groupnorm: bool = True,
        act_cls: Type[nn.Module] = nn.SiLU,
        act_kwargs: Optional[Dict] = None,
        mlp_hidden: Sequence[int] = (
            1024,
            1024,
        ),
    ):
        super().__init__(observation_space, features_dim=out_dim)
        C, H, W = observation_space.shape
        gain = _calc_gain(act_cls, act_kwargs)

        def ConvBlock(cin, cout, k, s, p):
            layers = [
                nn.Conv2d(cin, cout, kernel_size=k, stride=s, padding=p, bias=True)
            ]
            if use_groupnorm:
                layers.append(nn.GroupNorm(_gn_groups(cout), cout))
            layers.append(act_cls(**(act_kwargs or {})))
            block = nn.Sequential(*layers)
            block.apply(lambda m: _ortho_init(m, gain=gain))
            return block

        # ---- CNN backbone ----
        self.backbone = nn.Sequential(
            ConvBlock(C, 32, k=5, s=2, p=2),  # ~ H/2,  W/2
            ConvBlock(32, 64, k=3, s=2, p=1),  # ~ H/4,  W/4
            ConvBlock(64, 128, k=3, s=2, p=1),  # ~ H/8,  W/8
            ConvBlock(128, 256, k=3, s=2, p=1),  # ~ H/16, W/16
        )
        self.flatten = nn.Flatten()

        # ---- Probe flattened size ----
        with th.no_grad():
            dummy = th.zeros(1, C, H, W, dtype=th.float32)
            flat_dim = self.flatten(self.backbone(dummy)).shape[1]

        # ---- MLP ----
        h1, h2 = mlp_hidden
        self.mlp = nn.Sequential(
            nn.Linear(flat_dim, h1),
            act_cls(**(act_kwargs or {})),
            nn.Linear(h1, h2),
            act_cls(**(act_kwargs or {})),
            nn.Linear(h2, out_dim),
        )

        for m in self.mlp:
            if isinstance(m, nn.Linear):
                _ortho_init(m, gain=gain)

        self._features_dim = out_dim

    @property
    def features_dim(self) -> int:
        return self._features_dim

    def forward(self, obs: th.Tensor) -> th.Tensor:
        x = self.flatten(self.backbone(obs))  # (B, flat_dim)
        x = self.mlp(x)  # (B, out_dim)
        return x


class DepthwiseExtractor(BaseFeaturesExtractor):
    """
    Depthwise-separable CNN -> Adaptive Pool -> Flatten (~2-3k) -> 3-layer MLP -> features_dim.

    Args:
      features_dim: final output size returned to the policy (e.g., 400).
      base_channels: width of the CNN stem (keeps it light).
      use_depthwise: use depthwise+pointwise convs for efficiency.
      pool_out: (H, W) output of AdaptiveAvgPool2d; controls flattened size.
      head_channels: channels after the last 1x1 conv before pooling; also controls flattened size.
      mlp_hidden: 2-tuple for the 3-layer MLP (h1, h2).

    Notes:
      - Flattened size ~= head_channels * pool_out[0] * pool_out[1].
      - With (head_channels=32, pool_out=(12, 8)) -> 32*12*8 = 3072 features into MLP.
      - Uses BN after each conv; conv biases are disabled.
    """

    def __init__(
        self,
        observation_space: spaces.Box,
        features_dim: int = 400,
        base_channels: int = 32,
        use_depthwise: bool = True,
        pool_out: tuple[int, int] = (12, 8),
        head_channels: int = 32,
        mlp_hidden: tuple[int, int] = (1024, 512),
    ):
        assert isinstance(observation_space, spaces.Box)
        super().__init__(observation_space, features_dim)

        C, H, W = observation_space.shape
        Act = nn.SiLU

        def conv3x3(cin, cout, stride=1, depthwise=False):
            if depthwise:
                return nn.Sequential(
                    nn.Conv2d(
                        cin, cin, 3, stride=stride, padding=1, groups=cin, bias=False
                    ),
                    nn.BatchNorm2d(cin),
                    Act(),
                    nn.Conv2d(cin, cout, 1, bias=False),
                    nn.BatchNorm2d(cout),
                    Act(),
                )
            else:
                return nn.Sequential(
                    nn.Conv2d(cin, cout, 3, stride=stride, padding=1, bias=False),
                    nn.BatchNorm2d(cout),
                    Act(),
                )

        c1, c2, c3, c4 = (
            base_channels,
            base_channels * 2,
            base_channels * 4,
            base_channels * 4,
        )

        # /8 backbone: strides 2,2,2,1
        self.backbone = nn.Sequential(
            conv3x3(C, c1, stride=2, depthwise=use_depthwise),  # /2
            conv3x3(c1, c2, stride=2, depthwise=use_depthwise),  # /4
            conv3x3(c2, c3, stride=2, depthwise=use_depthwise),  # /8
            conv3x3(c3, c4, stride=1, depthwise=use_depthwise),  # keep /8
        )

        # 1x1 head to control channel count before pooling
        self.head1x1 = nn.Sequential(
            nn.Conv2d(c4, head_channels, 1, bias=False),
            nn.BatchNorm2d(head_channels),
            Act(),
        )

        # Fix spatial size -> controls flattened length
        self.pool_small = nn.AdaptiveAvgPool2d(pool_out)

        # Compute flattened size and build 3-layer MLP to compress to features_dim
        flat_dim = head_channels * pool_out[0] * pool_out[1]
        h1, h2 = mlp_hidden
        self.mlp = nn.Sequential(
            nn.Linear(flat_dim, h1),
            Act(),
            nn.Linear(h1, h2),
            Act(),
            nn.Linear(h2, features_dim),
        )

    def forward(self, x: th.Tensor) -> th.Tensor:
        x = self.backbone(x)
        x = self.head1x1(x)
        x = self.pool_small(x)
        x = th.flatten(x, 1)  # ~2–3k depending on head_channels * pool_out
        x = self.mlp(x)  # -> [B, features_dim]
        return x
