"""
U-Net with ResNet-50 encoder for deforestation segmentation.

Architecture: ResNet-50 encoder with symmetric U-Net decoder.
Input: 64×64×12 (bi-temporal Sentinel-2 patch pairs)
Output: Binary segmentation mask (deforested / intact)

The model uses a ResNet-50 backbone pre-trained on ImageNet,
with skip connections to a symmetric decoder for dense predictions.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
from typing import List


class ConvBlock(nn.Module):
    """Double convolution block with batch normalization."""

    def __init__(self, in_channels: int, out_channels: int):
        """
        Args:
            in_channels: Number of input channels
            out_channels: Number of output channels
        """
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu(x)
        return x


class DecoderBlock(nn.Module):
    """Decoder block with upsampling and skip connection."""

    def __init__(self, in_channels: int, skip_channels: int, out_channels: int):
        """
        Args:
            in_channels: Number of input channels from previous decoder level
            skip_channels: Number of channels from skip connection
            out_channels: Number of output channels
        """
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)
        self.conv_block = ConvBlock(in_channels + skip_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.upsample(x)
        x = torch.cat([x, skip], dim=1)
        x = self.conv_block(x)
        return x


class UNet(nn.Module):
    """U-Net deforestation detection model with ResNet-50 encoder."""

    def __init__(self, in_channels: int = 12, out_channels: int = 2):
        """
        Initialize U-Net model.

        Args:
            in_channels: Number of input channels (12 for bi-temporal S2)
            out_channels: Number of output classes (2 for binary segmentation)
        """
        super().__init__()

        # Encoder: ResNet-50
        resnet50 = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)

        # Adapt first conv layer for 12-channel input
        original_conv = resnet50.conv1
        self.initial_conv = nn.Conv2d(
            in_channels,
            64,
            kernel_size=7,
            stride=2,
            padding=3,
            bias=False
        )
        # Initialize with mean of pre-trained weights (average across input channels)
        with torch.no_grad():
            weight = original_conv.weight.mean(dim=1, keepdim=True)
            self.initial_conv.weight.copy_(weight.repeat(1, in_channels // 3, 1, 1))

        self.bn1 = resnet50.bn1
        self.relu = resnet50.relu
        self.maxpool = resnet50.maxpool

        # ResNet layers (encoder)
        self.layer1 = resnet50.layer1  # 64 channels
        self.layer2 = resnet50.layer2  # 256 channels
        self.layer3 = resnet50.layer3  # 512 channels
        self.layer4 = resnet50.layer4  # 2048 channels

        # Decoder blocks
        # Layer4 output: (B, 2048, 4, 4)
        self.decoder4 = DecoderBlock(2048, 512, 512)  # -> (B, 512, 8, 8)
        self.decoder3 = DecoderBlock(512, 256, 256)   # -> (B, 256, 16, 16)
        self.decoder2 = DecoderBlock(256, 64, 128)    # -> (B, 128, 32, 32)
        self.decoder1 = DecoderBlock(128, 64, 64)     # -> (B, 64, 64, 64)

        # Final classification head
        self.final_conv = nn.Sequential(
            nn.Conv2d(64, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, out_channels, kernel_size=1)
        )

        self.out_channels = out_channels
        self._freeze_bn()

    def _freeze_bn(self) -> None:
        """Freeze batch normalization layers."""
        for m in self.modules():
            if isinstance(m, nn.BatchNorm2d):
                m.eval()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through U-Net.

        Args:
            x: Input tensor of shape (B, 12, 64, 64)

        Returns:
            Output logits of shape (B, 2, 64, 64)
        """
        # Encoder
        e0 = self.initial_conv(x)      # (B, 64, 32, 32)
        e0 = self.bn1(e0)
        e0 = self.relu(e0)
        e0 = self.maxpool(e0)          # (B, 64, 16, 16)

        e1 = self.layer1(e0)           # (B, 64, 16, 16)
        e2 = self.layer2(e1)           # (B, 256, 8, 8)
        e3 = self.layer3(e2)           # (B, 512, 4, 4)
        e4 = self.layer4(e3)           # (B, 2048, 2, 2)

        # Decoder with skip connections
        d4 = self.decoder4(e4, e3)     # (B, 512, 4, 4)
        d3 = self.decoder3(d4, e2)     # (B, 256, 8, 8)
        d2 = self.decoder2(d3, e1)     # (B, 128, 16, 16)
        d1 = self.decoder1(d2, e0)     # (B, 64, 32, 32)

        # Upsample to original size
        d1 = F.interpolate(d1, scale_factor=2, mode='bilinear', align_corners=False)  # (B, 64, 64, 64)

        # Final classification
        output = self.final_conv(d1)   # (B, 2, 64, 64)

        return output

    def freeze_encoder(self) -> None:
        """Freeze encoder weights for transfer learning."""
        # Freeze all encoder layers
        self.initial_conv.requires_grad_(False)
        self.bn1.requires_grad_(False)
        self.layer1.requires_grad_(False)
        self.layer2.requires_grad_(False)
        self.layer3.requires_grad_(False)
        self.layer4.requires_grad_(False)

    def unfreeze_encoder(self) -> None:
        """Unfreeze encoder weights for fine-tuning."""
        self.initial_conv.requires_grad_(True)
        self.bn1.requires_grad_(True)
        self.layer1.requires_grad_(True)
        self.layer2.requires_grad_(True)
        self.layer3.requires_grad_(True)
        self.layer4.requires_grad_(True)

    def freeze_decoder(self) -> None:
        """Freeze decoder weights."""
        self.decoder4.requires_grad_(False)
        self.decoder3.requires_grad_(False)
        self.decoder2.requires_grad_(False)
        self.decoder1.requires_grad_(False)
        self.final_conv.requires_grad_(False)

    def unfreeze_decoder(self) -> None:
        """Unfreeze decoder weights."""
        self.decoder4.requires_grad_(True)
        self.decoder3.requires_grad_(True)
        self.decoder2.requires_grad_(True)
        self.decoder1.requires_grad_(True)
        self.final_conv.requires_grad_(True)

    def get_encoder_params(self) -> List[torch.nn.Parameter]:
        """Get encoder parameters for selective optimization."""
        params = []
        for m in [self.initial_conv, self.bn1, self.layer1, self.layer2, self.layer3, self.layer4]:
            params.extend(m.parameters())
        return params

    def get_decoder_params(self) -> List[torch.nn.Parameter]:
        """Get decoder parameters for selective optimization."""
        params = []
        for m in [self.decoder4, self.decoder3, self.decoder2, self.decoder1, self.final_conv]:
            params.extend(m.parameters())
        return params


def create_unet(
    in_channels: int = 12,
    out_channels: int = 2,
    pretrained: bool = True,
    freeze_encoder: bool = False
) -> UNet:
    """
    Factory function to create U-Net model.

    Args:
        in_channels: Number of input channels (12 for bi-temporal S2)
        out_channels: Number of output classes (2 for binary segmentation)
        pretrained: Whether to use ImageNet pre-trained ResNet-50
        freeze_encoder: Whether to freeze encoder weights initially

    Returns:
        Initialized U-Net model
    """
    model = UNet(in_channels=in_channels, out_channels=out_channels)

    if freeze_encoder:
        model.freeze_encoder()

    return model


if __name__ == "__main__":
    # Test model creation and forward pass
    print("Creating U-Net model...")
    model = create_unet()
    print(f"Model created with {sum(p.numel() for p in model.parameters()) / 1e6:.2f}M parameters")

    print("\nTesting forward pass...")
    x = torch.randn(4, 12, 64, 64)
    print(f"Input shape: {x.shape}")

    output = model(x)
    print(f"Output shape: {output.shape}")
    print(f"Output range: [{output.min():.3f}, {output.max():.3f}]")

    # Test encoder freezing
    print("\nTesting freeze/unfreeze...")
    model.freeze_encoder()
    print(f"Encoder frozen: {not model.layer1[0].conv1.weight.requires_grad}")

    model.unfreeze_encoder()
    print(f"Encoder unfrozen: {model.layer1[0].conv1.weight.requires_grad}")

    print("\n✅ Model test complete!")
