"""Pretrained visual backbones adapted as SB3 feature extractors.

Currently includes a MobileNetV3-Small based extractor that returns the
flattened feature vector from its last convolutional block. Intended for
freezing and reuse in RL policies.
"""

import torch
import torch.nn as nn
import torchvision.transforms as T

from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
from torchvision.models.feature_extraction import create_feature_extractor
from gymnasium import spaces

from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


class MobileNetv3FeatureExtractor(BaseFeaturesExtractor):
    """
    Runs inputs through a pretrained model up to its 'flatten' node,
    returning a (batch, feature_dim) tensor.
    """

    def __init__(
        self,
        observation_space: spaces.Box,
        pretrained: bool = True,
        freeze_backbone: bool = True,
    ):
        # obs_space.shape == (C, H, W)
        super().__init__(observation_space, features_dim=1)  # placeholder

        # 1) Instantiate full MobileNetV3-Small
        backbone = mobilenet_v3_small(
            weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1
        ).eval()

        if freeze_backbone:
            for p in backbone.parameters():
                p.requires_grad = False

        # 2) Extract last conv block features
        self.body = create_feature_extractor(
            backbone, return_nodes={"flatten": "features"}
        )

        # 3) Dry run to extract shape
        with torch.no_grad():
            # a single dummy batch
            C, H, W = observation_space.shape
            dummy = torch.zeros(1, C, H, W)
            out = self.body(dummy)
            self._features_dim = out["features"].shape[1]

        # 4) Preprocess
        self.preprocess = T.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        """
        observations: uint8 or float tensor with shape (batch, C, H, W), values in [0–255] or [0–1]
        returns: (batch, features_dim)
        """
        if observations.dtype == torch.uint8:
            observations = observations.float() / 255.0

        x = self.preprocess(observations)
        feats = self.body(x)["features"]
        return feats

    @property
    def features_dim(self) -> int:
        return self._features_dim