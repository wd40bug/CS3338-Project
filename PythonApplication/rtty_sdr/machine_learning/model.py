import os
os.environ["SRU_DISABLE_CUDA"] = "1"
os.environ["SRU_DISABLE_JIT"] = "1"
from sru import SRU
SRU.use_torchscript = False
import torch
import torch.nn as nn
#  $env:Path += ";C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.xx.xxxxx\bin\Hostx64\x64"
class SRUModel(nn.Module):
    def __init__(self, vocab_size,
                 embedding_dim, hidden_dim,
                 num_layers, dropout, bidirectional):
        super().__init__()
        self.embedding = nn.Embedding(num_embeddings=vocab_size,embedding_dim=embedding_dim)
        self.sru = SRU(input_size=embedding_dim,
                       hidden_size=hidden_dim,
                       num_layers=num_layers,
                       dropout=dropout, bidirectional=bidirectional)
        self.layernorm = nn.LayerNorm(hidden_dim*2 if bidirectional else hidden_dim)
        self.linear = nn.Linear(in_features=hidden_dim*2 if bidirectional else hidden_dim, out_features=vocab_size)

    def forward(self,x):
        x = self.embedding(x)
        x = x.transpose(0, 1)
        x, _ = self.sru(x) # returns hidden output and last hidden state as tensors
        x = x.transpose(0, 1)
        x = self.layernorm(x)
        x = self.linear(x)
        return x # logits, not probabilities since no softmax layer