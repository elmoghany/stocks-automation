"""RL-SERIES (2026-09-16): EIIE-style shared per-candidate evaluator.

Jiang, Xu & Liang 2017 (arXiv 1706.10059) score every asset with the SAME
small network -- an "ensemble of identical independent evaluators" -- so the
model learns "what a good candidate looks like" rather than "what slot 3
usually does". That is the one idea in the portfolio-RL literature that
transfers cleanly to a variable-size candidate set, and it is the reason a
flat MLP over our 209-dim observation is a weak architecture here: slot k's
15 features sit at a fixed offset, so a plain MlpPolicy must relearn the same
function ten times.

PGPortfolio itself is GPL-3.0 and TensorFlow 1.x and its published result has
a public replication failure (wassname/rl-portfolio-management), so nothing
is copied from it. This is a clean-room torch features extractor for SB3:

  slot block   [B, K, NF]  -> shared MLP -> per-slot embedding and a shared
                             scalar score (one number per candidate)
  position blk [B, P, NG]  -> shared MLP -> per-position embedding + score
  globals      [B, NGLOB]  -> MLP -> context

Output = [K slot scores | P position scores | context], so the policy head
sees one comparable number per tradeable object plus shared context. Weight
sharing across slots/positions is exact.
"""
import sys
from pathlib import Path

import torch
import torch.nn as nn
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import env as E                                             # noqa: E402


def _mlp(i, h, o):
    return nn.Sequential(nn.Linear(i, h), nn.Tanh(), nn.Linear(h, o), nn.Tanh())


class EIIEExtractor(BaseFeaturesExtractor):
    def __init__(self, observation_space: spaces.Box, hidden: int = 64,
                 ctx: int = 32):
        K, NF, P, NG, G = E.K_SLOTS, E.NF, E.P_SLOTS, E.NG, E.NGLOB
        n = observation_space.shape[0]
        self.leak = n - (K * NF + K + P * NG + G)
        assert self.leak in (0, K), f"unexpected obs width {n}"
        super().__init__(observation_space, features_dim=K + P + ctx)
        self.K, self.NF, self.P, self.NG, self.G = K, NF, P, NG, G
        slot_in = NF + 1 + (1 if self.leak else 0)   # + availability (+ leak)
        self.slot = _mlp(slot_in, hidden, hidden)
        self.slot_score = nn.Linear(hidden, 1)
        self.pos = _mlp(NG, hidden, hidden)
        self.pos_score = nn.Linear(hidden, 1)
        self.ctx = nn.Sequential(
            nn.Linear(G + hidden + hidden, ctx), nn.Tanh())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        K, NF, P, NG, G = self.K, self.NF, self.P, self.NG, self.G
        i = 0
        f = x[:, i:i + K * NF].reshape(-1, K, NF); i += K * NF
        av = x[:, i:i + K].reshape(-1, K, 1); i += K
        g = x[:, i:i + P * NG].reshape(-1, P, NG); i += P * NG
        gl = x[:, i:i + G]; i += G
        parts = [f, av]
        if self.leak:
            parts.append(x[:, i:i + K].reshape(-1, K, 1))
        se = self.slot(torch.cat(parts, dim=2))              # [B,K,H]
        pe = self.pos(g)                                     # [B,P,H]
        s = self.slot_score(se).squeeze(-1)                  # [B,K]
        p = self.pos_score(pe).squeeze(-1)                   # [B,P]
        c = self.ctx(torch.cat([gl, se.mean(1), pe.mean(1)], dim=1))
        return torch.cat([s, p, c], dim=1)


EIIE_KW = dict(features_extractor_class=EIIEExtractor,
               features_extractor_kwargs=dict(hidden=64, ctx=32),
               net_arch=[64])
