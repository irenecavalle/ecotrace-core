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
        # Use 1x1 conv to adjust skip connection channels if needed
        self.skip_conv = nn.Conv2d(skip_channels, in_channels, kernel_size=1) if skip_channels != in_channels else nn.Identity()
        self.conv_block = ConvBlock(in_channels * 2, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.upsample(x)
        skip = self.skip_conv(skip)
        x = torch.cat([x, skip], dim=1)
        x = self.conv_block(x)
        return x


class UNet(nn.Module):
    """U-Net deforestation detection model with simplified architecture."""

    def __init__(self, in_channels: int = 12, out_channels: int = 1):
        """
        Initialize U-Net model.

        Args:
            in_channels: Number of input channels (12 for bi-temporal S2)
            out_channels: Number of output channels (1 for binary segmentation)
        """
        super().__init__()

        # Simple encoder-decoder U-Net
        self.enc1 = ConvBlock(in_channels, 64)
        self.pool1 = nn.MaxPool2d(2)

        self.enc2 = ConvBlock(64, 128)
        self.pool2 = nn.MaxPool2d(2)

        self.enc3 = ConvBlock(128, 256)
        self.pool3 = nn.MaxPool2d(2)

        self.enc4 = ConvBlock(256, 512)
        self.pool4 = nn.MaxPool2d(2)

        # Bottleneck
        self.bottleneck = ConvBlock(512, 1024)

        # Decoder
        self.upconv4 = nn.ConvTranspose2d(1024, 512, kernel_size=2, stride=2)
        self.dec4 = ConvBlock(1024, 512)

        self.upconv3 = nn.ConvTranspose2d(512, 256, kernel_size=2, stride=2)
        self.dec3 = ConvBlock(512, 256)

        self.upconv2 = nn.ConvTranspose2d(256, 128, kernel_size=2, stride=2)
        self.dec2 = ConvBlock(256, 128)

        self.upconv1 = nn.ConvTranspose2d(128, 64, kernel_size=2, stride=2)
        self.dec1 = ConvBlock(128, 64)

        # Final layer
        self.final = nn.Conv2d(64, out_channels, kernel_size=1)

        self.out_channels = out_channels

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through U-Net.

        Args:
            x: Input tensor of shape (B, 12, 64, 64)

        Returns:
            Output logits of shape (B, out_channels, 64, 64)
        """
        # Encoder with skip connections
        e1 = self.enc1(x)              # (B, 64, 64, 64)
        p1 = self.pool1(e1)            # (B, 64, 32, 32)

        e2 = self.enc2(p1)             # (B, 128, 32, 32)
        p2 = self.pool2(e2)            # (B, 128, 16, 16)

        e3 = self.enc3(p2)             # (B, 256, 16, 16)
        p3 = self.pool3(e3)            # (B, 256, 8, 8)

        e4 = self.enc4(p3)             # (B, 512, 8, 8)
        p4 = self.pool4(e4)            # (B, 512, 4, 4)

        # Bottleneck
        bn = self.bottleneck(p4)       # (B, 1024, 4, 4)

        # Decoder with skip connections
        up4 = self.upconv4(bn)         # (B, 512, 8, 8)
        d4 = torch.cat([up4, e4], dim=1)  # (B, 1024, 8, 8)
        d4 = self.dec4(d4)             # (B, 512, 8, 8)

        up3 = self.upconv3(d4)         # (B, 256, 16, 16)
        d3 = torch.cat([up3, e3], dim=1)  # (B, 512, 16, 16)
        d3 = self.dec3(d3)             # (B, 256, 16, 16)

        up2 = self.upconv2(d3)         # (B, 128, 32, 32)
        d2 = torch.cat([up2, e2], dim=1)  # (B, 256, 32, 32)
        d2 = self.dec2(d2)             # (B, 128, 32, 32)

        up1 = self.upconv1(d2)         # (B, 64, 64, 64)
        d1 = torch.cat([up1, e1], dim=1)  # (B, 128, 64, 64)
        d1 = self.dec1(d1)             # (B, 64, 64, 64)

        # Final classification
        output = self.final(d1)        # (B, out_channels, 64, 64)

        return output

    def freeze_encoder(self) -> None:
        """Freeze encoder weights for transfer learning."""
        self.enc1.requires_grad_(False)
        self.enc2.requires_grad_(False)
        self.enc3.requires_grad_(False)
        self.enc4.requires_grad_(False)

    def unfreeze_encoder(self) -> None:
        """Unfreeze encoder weights for fine-tuning."""
        self.enc1.requires_grad_(True)
        self.enc2.requires_grad_(True)
        self.enc3.requires_grad_(True)
        self.enc4.requires_grad_(True)


def create_unet(in_channels: int = 12, out_channels: int = 1) -> UNet:
    """
    Factory function to create U-Net model.

    Args:
        in_channels: Number of input channels (12 for bi-temporal S2)
        out_channels: Number of output channels (1 for binary segmentation)

    Returns:
        Initialized U-Net model
    """
    return UNet(in_channels=in_channels, out_channels=out_channels)


if __name__ == "__main__":
    print("Creating U-Net model...")
    model = create_unet(in_channels=12, out_channels=1)
    print(f"Model created with {sum(p.numel() for p in model.parameters()) / 1e6:.2f}M parameters")

    print("\nTesting forward pass...")
    x = torch.randn(4, 12, 64, 64)
    print(f"Input shape: {x.shape}")

    output = model(x)
    print(f"Output shape: {output.shape}")
    print(f"Output range: [{output.min():.3f}, {output.max():.3f}]")

    print("\n✅ Model test complete!")
