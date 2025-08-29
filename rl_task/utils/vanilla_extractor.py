import torch as th
import torch.nn as nn
import torchvision.transforms as T

from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


def ortho_init(m, gain=th.sqrt(th.tensor(2.0))):
    if isinstance(m, (nn.Conv2d, nn.Linear)):
        nn.init.orthogonal_(m.weight, gain=float(gain))
        if m.bias is not None:
            nn.init.constant_(m.bias, 0.0)


class CustomExtractor(BaseFeaturesExtractor):
    """
    CNN feature extractor for visual observations.
    Produces a flat feature vector for SB3.
    """

    def __init__(self, observation_space: spaces.Box):
        super().__init__(observation_space, features_dim=1)

        C, H, W = observation_space.shape

        self.preprocess = T.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
        self.cnn = nn.Sequential(
            nn.Conv2d(C, 32, kernel_size=8, stride=4, padding=0),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, kernel_size=4, stride=2, padding=0),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=0),
            nn.ReLU(inplace=True),
            nn.Flatten(),
        )

        self.cnn.apply(ortho_init)

        # Compute output dim with a zero dummy
        with th.no_grad():
            sample = th.zeros(1, C, H, W, dtype=th.float32)
            feats = self.cnn(self.preprocess(sample))
            self._features_dim = feats.shape[1]

    @property
    def features_dim(self) -> int:
        return self._features_dim

    def forward(self, observations: th.Tensor) -> th.Tensor:
        x = self.preprocess(observations)
        return self.cnn(x)
