from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import nn


class MunicipalityLSTM(nn.Module):
    """Global municipality LSTM using temporal, current-period, and location inputs."""

    def __init__(
        self,
        sequence_features: int,
        current_features: int,
        location_count: int,
        hidden_size: int,
        embedding_size: int,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(sequence_features, hidden_size, batch_first=True)
        self.embedding = nn.Embedding(location_count, embedding_size)
        self.regressor = nn.Sequential(
            nn.Linear(hidden_size + embedding_size + current_features, 48),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(48, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Softplus(),
        )

    def forward(
        self,
        sequence: torch.Tensor,
        current: torch.Tensor,
        location_ids: torch.Tensor,
    ) -> torch.Tensor:
        _, (hidden, _) = self.lstm(sequence)
        combined = torch.cat(
            [hidden[-1], self.embedding(location_ids), current], dim=1
        )
        return self.regressor(combined).squeeze(1)


@dataclass(frozen=True)
class MetricSet:
    r2: float
    mae: float
    rmse: float
    wape: float
    smape: float

    def as_dict(self) -> dict[str, float]:
        return {
            "r2": self.r2,
            "mae": self.mae,
            "rmse": self.rmse,
            "wape": self.wape,
            "smape": self.smape,
        }
