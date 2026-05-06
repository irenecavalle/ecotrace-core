"""
Training loop for U-Net deforestation segmentation model.

Trains U-Net on synthetic bi-temporal Sentinel-2 patches for deforestation detection.
Includes synthetic data generation, training, validation, and evaluation metrics.
"""

import json
import logging
from pathlib import Path
from typing import Tuple, Dict, List

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import Adam

from src.models.unet import UNet, create_unet

logger = logging.getLogger(__name__)


class SyntheticDeforestationDataset(Dataset):
    """Generate synthetic deforestation patches for training."""

    def __init__(self, num_samples: int = 500, patch_size: int = 64, deforestation_ratio: float = 0.3):
        """
        Initialize synthetic dataset.

        Args:
            num_samples: Number of synthetic patches to generate
            patch_size: Patch size (64x64)
            deforestation_ratio: Fraction of patches with deforestation (30%)
        """
        self.num_samples = num_samples
        self.patch_size = patch_size
        self.deforestation_ratio = deforestation_ratio

        # Generate synthetic data
        self.patches, self.labels = self._generate_synthetic_data()

    def _generate_synthetic_data(self) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Generate synthetic bi-temporal Sentinel-2 patches.

        Returns:
            Tuple of (patches, labels) tensors
        """
        patches = []
        labels = []

        np.random.seed(42)

        num_deforested = int(self.num_samples * self.deforestation_ratio)
        num_intact = self.num_samples - num_deforested

        # Generate deforested patches (30%)
        for i in range(num_deforested):
            # Deforested patches: low vegetation (NDVI), high noise
            patch = self._create_deforested_patch()
            mask = self._create_deforested_mask()
            patches.append(patch)
            labels.append(mask)

        # Generate intact patches (70%)
        for i in range(num_intact):
            # Intact patches: high vegetation (NDVI), low noise
            patch = self._create_intact_patch()
            mask = self._create_intact_mask()
            patches.append(patch)
            labels.append(mask)

        patches = torch.from_numpy(np.stack(patches)).float()
        labels = torch.from_numpy(np.stack(labels)).float()

        return patches, labels

    def _create_deforested_patch(self) -> np.ndarray:
        """Create synthetic deforested patch (low vegetation, high degradation)."""
        # Bi-temporal: 6 bands at T1, 6 bands at T2
        patch = np.zeros((12, self.patch_size, self.patch_size), dtype=np.float32)

        # Bands: B2 (blue), B3 (green), B4 (red), B8 (NIR), B11 (SWIR1), B12 (SWIR2)
        # T1 (indices 0-5): pre-deforestation
        patch[0] = np.random.normal(0.2, 0.05, (self.patch_size, self.patch_size))  # B2
        patch[1] = np.random.normal(0.3, 0.05, (self.patch_size, self.patch_size))  # B3
        patch[2] = np.random.normal(0.2, 0.05, (self.patch_size, self.patch_size))  # B4
        patch[3] = np.random.normal(0.4, 0.05, (self.patch_size, self.patch_size))  # B8 (NIR)
        patch[4] = np.random.normal(0.25, 0.05, (self.patch_size, self.patch_size))  # B11
        patch[5] = np.random.normal(0.15, 0.05, (self.patch_size, self.patch_size))  # B12

        # T2 (indices 6-11): post-deforestation (low vegetation, high soil exposure)
        patch[6] = np.random.normal(0.25, 0.05, (self.patch_size, self.patch_size))  # B2 (higher)
        patch[7] = np.random.normal(0.35, 0.05, (self.patch_size, self.patch_size))  # B3 (higher)
        patch[8] = np.random.normal(0.28, 0.05, (self.patch_size, self.patch_size))  # B4 (higher)
        patch[9] = np.random.normal(0.25, 0.05, (self.patch_size, self.patch_size))  # B8 (much lower)
        patch[10] = np.random.normal(0.3, 0.05, (self.patch_size, self.patch_size))  # B11 (higher)
        patch[11] = np.random.normal(0.2, 0.05, (self.patch_size, self.patch_size))  # B12 (higher)

        # Clip to valid range
        patch = np.clip(patch, 0, 1)

        return patch

    def _create_intact_patch(self) -> np.ndarray:
        """Create synthetic intact patch (high vegetation, stable)."""
        patch = np.zeros((12, self.patch_size, self.patch_size), dtype=np.float32)

        # T1: healthy vegetation
        patch[0] = np.random.normal(0.15, 0.03, (self.patch_size, self.patch_size))  # B2
        patch[1] = np.random.normal(0.2, 0.03, (self.patch_size, self.patch_size))  # B3
        patch[2] = np.random.normal(0.1, 0.03, (self.patch_size, self.patch_size))  # B4 (low red)
        patch[3] = np.random.normal(0.5, 0.05, (self.patch_size, self.patch_size))  # B8 (high NIR)
        patch[4] = np.random.normal(0.2, 0.03, (self.patch_size, self.patch_size))  # B11
        patch[5] = np.random.normal(0.1, 0.03, (self.patch_size, self.patch_size))  # B12

        # T2: still healthy vegetation (stable)
        patch[6] = np.random.normal(0.15, 0.03, (self.patch_size, self.patch_size))  # B2
        patch[7] = np.random.normal(0.2, 0.03, (self.patch_size, self.patch_size))  # B3
        patch[8] = np.random.normal(0.1, 0.03, (self.patch_size, self.patch_size))  # B4
        patch[9] = np.random.normal(0.52, 0.05, (self.patch_size, self.patch_size))  # B8
        patch[10] = np.random.normal(0.19, 0.03, (self.patch_size, self.patch_size))  # B11
        patch[11] = np.random.normal(0.09, 0.03, (self.patch_size, self.patch_size))  # B12

        patch = np.clip(patch, 0, 1)

        return patch

    def _create_deforested_mask(self) -> np.ndarray:
        """Create binary segmentation mask for deforested patch (1=deforested)."""
        mask = np.ones((1, self.patch_size, self.patch_size), dtype=np.float32)
        # Add some variation (not all pixels deforested)
        mask[0, :, :] = np.random.choice([0.8, 0.9, 1.0], (self.patch_size, self.patch_size))
        return mask

    def _create_intact_mask(self) -> np.ndarray:
        """Create binary segmentation mask for intact patch (0=not deforested)."""
        mask = np.zeros((1, self.patch_size, self.patch_size), dtype=np.float32)
        # Add some variation (not completely clean)
        mask[0, :, :] = np.random.choice([0.0, 0.1, 0.05], (self.patch_size, self.patch_size))
        return mask

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.patches[idx], self.labels[idx]


class UNetTrainer:
    """Trainer for U-Net deforestation model."""

    def __init__(self, device: str = None, learning_rate: float = 0.001):
        """
        Initialize trainer.

        Args:
            device: Torch device (cuda or cpu), auto-detect if None
            learning_rate: Learning rate for optimizer
        """
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = create_unet(in_channels=12, out_channels=1)
        self.model = self.model.to(self.device)

        self.criterion = nn.BCEWithLogitsLoss()
        self.optimizer = Adam(self.model.parameters(), lr=learning_rate)

        self.history = {
            'train_loss': [],
            'test_loss': [],
            'test_f1': [],
            'test_iou': []
        }

        logger.info(f"Using device: {self.device}")
        logger.info(f"Model has {sum(p.numel() for p in self.model.parameters()) / 1e6:.2f}M parameters")

    def train_epoch(self, train_loader: DataLoader) -> float:
        """
        Train for one epoch.

        Args:
            train_loader: DataLoader for training data

        Returns:
            Average loss for the epoch
        """
        self.model.train()
        total_loss = 0.0

        for batch_idx, (patches, labels) in enumerate(train_loader):
            patches = patches.to(self.device)
            labels = labels.to(self.device)

            self.optimizer.zero_grad()
            outputs = self.model(patches)
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)
        return avg_loss

    def evaluate(self, test_loader: DataLoader) -> Dict[str, float]:
        """
        Evaluate model on test set.

        Args:
            test_loader: DataLoader for test data

        Returns:
            Dict with evaluation metrics (loss, F1, IOU)
        """
        self.model.eval()
        total_loss = 0.0
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for patches, labels in test_loader:
                patches = patches.to(self.device)
                labels = labels.to(self.device)

                outputs = self.model(patches)
                loss = self.criterion(outputs, labels)
                total_loss += loss.item()

                # Binary predictions (threshold at 0.5)
                preds = (outputs > 0.0).float()
                all_preds.append(preds.cpu())
                all_labels.append(labels.cpu())

        avg_loss = total_loss / len(test_loader)
        preds = torch.cat(all_preds, dim=0).numpy()
        labels = torch.cat(all_labels, dim=0).numpy()

        f1 = self._compute_f1(preds, labels)
        iou = self._compute_iou(preds, labels)

        return {
            'loss': avg_loss,
            'f1': f1,
            'iou': iou
        }

    @staticmethod
    def _compute_f1(preds: np.ndarray, labels: np.ndarray) -> float:
        """Compute F1 score."""
        preds_flat = preds.flatten()
        labels_flat = labels.flatten()

        tp = np.sum((preds_flat > 0.5) & (labels_flat > 0.5))
        fp = np.sum((preds_flat > 0.5) & (labels_flat <= 0.5))
        fn = np.sum((preds_flat <= 0.5) & (labels_flat > 0.5))

        precision = tp / (tp + fp + 1e-8)
        recall = tp / (tp + fn + 1e-8)
        f1 = 2 * (precision * recall) / (precision + recall + 1e-8)

        return float(f1)

    @staticmethod
    def _compute_iou(preds: np.ndarray, labels: np.ndarray) -> float:
        """Compute Intersection over Union (Jaccard index)."""
        preds_flat = preds.flatten()
        labels_flat = labels.flatten()

        intersection = np.sum((preds_flat > 0.5) & (labels_flat > 0.5))
        union = np.sum((preds_flat > 0.5) | (labels_flat > 0.5))

        iou = intersection / (union + 1e-8)

        return float(iou)

    def train(self, train_loader: DataLoader, test_loader: DataLoader, epochs: int = 10) -> Dict:
        """
        Full training loop.

        Args:
            train_loader: Training DataLoader
            test_loader: Test DataLoader
            epochs: Number of epochs

        Returns:
            Training history
        """
        for epoch in range(epochs):
            train_loss = self.train_epoch(train_loader)
            test_metrics = self.evaluate(test_loader)

            self.history['train_loss'].append(train_loss)
            self.history['test_loss'].append(test_metrics['loss'])
            self.history['test_f1'].append(test_metrics['f1'])
            self.history['test_iou'].append(test_metrics['iou'])

            print(
                f"Epoch {epoch + 1:2d}/{epochs} | "
                f"Train Loss: {train_loss:.4f} | "
                f"Test Loss: {test_metrics['loss']:.4f} | "
                f"F1: {test_metrics['f1']:.4f} | "
                f"IOU: {test_metrics['iou']:.4f}"
            )

        return self.history

    def save_model(self, path: Path) -> None:
        """Save model checkpoint."""
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), str(path))
        logger.info(f"Model saved to {path}")

    def save_metrics(self, path: Path) -> None:
        """Save training metrics to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.history, f, indent=2)
        logger.info(f"Metrics saved to {path}")


def main():
    """Main training entry point."""
    print("\n" + "="*80)
    print("U-NET DEFORESTATION DETECTION TRAINING")
    print("="*80 + "\n")

    print("[*] Generating synthetic dataset...")
    dataset = SyntheticDeforestationDataset(num_samples=500, deforestation_ratio=0.3)
    print(f"    Generated {len(dataset)} patches (30% deforested, 70% intact)")

    # Split 80% train, 20% test
    train_size = int(0.8 * len(dataset))
    test_size = len(dataset) - train_size
    train_dataset, test_dataset = torch.utils.data.random_split(
        dataset,
        [train_size, test_size]
    )

    print(f"    Train: {train_size} samples, Test: {test_size} samples")

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

    print("\n[*] Initializing model...")
    trainer = UNetTrainer(learning_rate=0.001)

    print("\n[*] Training for 10 epochs...\n")
    history = trainer.train(train_loader, test_loader, epochs=10)

    # Save model and metrics
    print("\n[*] Saving results...")
    model_path = Path("models/unet_deforestation_v1.pt")
    metrics_path = Path("results/unet_metrics.json")

    trainer.save_model(model_path)
    trainer.save_metrics(metrics_path)

    # Print final metrics
    print("\n" + "="*80)
    print("FINAL METRICS")
    print("="*80)
    print(f"Final Train Loss:  {history['train_loss'][-1]:.4f}")
    print(f"Final Test Loss:   {history['test_loss'][-1]:.4f}")
    print(f"Final F1 Score:    {history['test_f1'][-1]:.4f}")
    print(f"Final IOU:         {history['test_iou'][-1]:.4f}")
    print("="*80 + "\n")

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    exit(main())
