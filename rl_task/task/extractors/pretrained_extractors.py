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


# class DINOv3FeatureExtractor(BaseFeaturesExtractor):

#     def __init__(
#         self,
#         observation_space: spaces.Box,
#         model_name: str = "facebook/dinov3-convnext-tiny-pretrain-lvd1689m",
#     ):
#         # get output embedding size dynamically via a dummy forward
#         super().__init__(observation_space, features_dim=1)  # placeholder

#         load_dotenv()
#         token = os.environ.get("HF_TOKEN")

#         # Load HF processor and model
#         self.processor = AutoImageProcessor.from_pretrained(
#             model_name,
#             use_auth_token=token,
#         )
#         self.model = AutoModel.from_pretrained(
#             model_name,
#             use_auth_token=token,
#         )

#         # Freeze backbone
#         for param in self.model.parameters():
#             param.requires_grad = False

#         # Figure out feature dimension (pooled output size)
#         dummy_image = torch.zeros(1, *observation_space.shape, dtype=torch.float32)
#         inputs = self.processor(
#             images=dummy_image.permute(0, 2, 3, 1).numpy(), return_tensors="pt"
#         )
#         with torch.no_grad():
#             outputs = self.model(**inputs)
#         n_features = outputs.pooler_output.shape[-1]

#         # Update SB3 features_dim
#         self._features_dim = n_features

#     @property
#     def features_dim(self):
#         return self._features_dim

#     def forward(self, observations: torch.Tensor) -> torch.Tensor:
#         # Convert from (B, C, H, W) → processor expects (B, H, W, C)
#         inputs = self.processor(
#             images=observations.permute(0, 2, 3, 1).cpu().numpy(), return_tensors="pt"
#         ).to(self.model.device)

#         with torch.no_grad():
#             outputs = self.model(**inputs)

#         return outputs.pooler_output


# class DINOv2FeatureExtractor(BaseFeaturesExtractor):
#     """
#     SB3-compatible feature extractor using a frozen DINOv2 backbone.
#     """

#     def __init__(
#         self, observation_space: spaces.Box, model_name="facebook/dinov2-small"
#     ):
#         # Call parent constructor with placeholder features_dim (will update later)
#         super().__init__(observation_space, features_dim=1)

#         # Load processor and model
#         self.processor = AutoImageProcessor.from_pretrained(model_name)
#         self.model = AutoModel.from_pretrained(model_name)

#         # Freeze the backbone
#         for param in self.model.parameters():
#             param.requires_grad = False

#         # Determine the feature dimension using a dummy forward pass
#         dummy_img = torch.zeros((1, *observation_space.shape), dtype=torch.float32)
#         # DINO expects (B,H,W,C), so permute channels
#         inputs = self.processor(
#             images=dummy_img.permute(0, 2, 3, 1).numpy(), return_tensors="pt"
#         )
#         with torch.no_grad():
#             outputs = self.model(**inputs)
#         self._features_dim = outputs.pooler_output.shape[-1]

#     @property
#     def features_dim(self) -> int:
#         return self._features_dim

#     def forward(self, observations: torch.Tensor) -> torch.Tensor:
#         inputs = self.processor(
#             images=observations.permute(0, 2, 3, 1).cpu().numpy(),
#             return_tensors="pt",
#             do_rescale=False,
#         ).to(self.model.device)
#         with torch.no_grad():
#             outputs = self.model(**inputs)
#         return outputs.pooler_output
