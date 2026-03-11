import torch
import torch.nn as nn
from typing import List, Optional


class Autoencoder(nn.Module):
    def __init__(self, input_dim: int = 4, encoding_dims: List[int] = None, l2_reg: float = 0.001):
        super(Autoencoder, self).__init__()
        
        if encoding_dims is None:
            encoding_dims = [8, 4, 2]
        
        self.input_dim = input_dim
        self.encoding_dims = encoding_dims
        self.l2_reg = l2_reg
        
        self.encoder = self._build_encoder()
        self.decoder = self._build_decoder()
    
    def _build_encoder(self) -> nn.Sequential:
        layers = []
        prev_dim = self.input_dim
        
        for i, dim in enumerate(self.encoding_dims):
            layers.append(nn.Linear(prev_dim, dim))
            
            # Add ReLU for all layers
            layers.append(nn.ReLU())
            
            # Add BatchNorm for all layers except bottleneck (last encoding layer)
            if i < len(self.encoding_dims) - 1:
                layers.append(nn.BatchNorm1d(dim, track_running_stats=True))
            
            prev_dim = dim
        
        return nn.Sequential(*layers)
    
    def _build_decoder(self) -> nn.Sequential:
        layers = []
        reversed_dims = list(reversed(self.encoding_dims))
        prev_dim = self.encoding_dims[-1]
        
        for i, dim in enumerate(reversed_dims):
            layers.append(nn.Linear(prev_dim, dim))
            
            # Add ReLU for hidden layers
            if i < len(reversed_dims) - 1:
                layers.append(nn.ReLU())
                layers.append(nn.BatchNorm1d(dim, track_running_stats=True))
            
            prev_dim = dim
        
        # Final output layer
        layers.append(nn.Linear(prev_dim, self.input_dim))
        layers.append(nn.Sigmoid())
        
        return nn.Sequential(*layers)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded
    
    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)
    
    def decode(self, encoded: torch.Tensor) -> torch.Tensor:
        return self.decoder(encoded)
    
    def compute_loss(self, x: torch.Tensor, x_reconstructed: torch.Tensor) -> torch.Tensor:
        mse_loss = nn.MSELoss()(x_reconstructed, x)
        
        l2_loss = torch.tensor(0.0, device=x.device)
        for param in self.parameters():
            l2_loss += torch.norm(param, 2)
        
        total_loss = mse_loss + self.l2_reg * l2_loss
        return total_loss
    
    def reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            reconstructed = self.forward(x)
            error = torch.mean((x - reconstructed) ** 2, dim=1)
        return error
    
    def save_model(self, path: str) -> None:
        torch.save({
            'model_state_dict': self.state_dict(),
            'input_dim': self.input_dim,
            'encoding_dims': self.encoding_dims,
            'l2_reg': self.l2_reg,
        }, path)
    
    @staticmethod
    def load_model(path: str, device: Optional[str] = None) -> 'Autoencoder':
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        checkpoint = torch.load(path, map_location=device)
        model = Autoencoder(
            input_dim=checkpoint['input_dim'],
            encoding_dims=checkpoint['encoding_dims'],
            l2_reg=checkpoint['l2_reg'],
        )
        model.load_state_dict(checkpoint['model_state_dict'])
        model.to(device)
        return model
    
    def get_device(self) -> str:
        return next(self.parameters()).device


class MetricAutoencoder(Autoencoder):
    def __init__(self, l2_reg: float = 0.001):
        super().__init__(
            input_dim=4,
            encoding_dims=[8, 4, 2],
            l2_reg=l2_reg,
        )
    
    @staticmethod
    def load_model(path: str, device: Optional[str] = None) -> 'MetricAutoencoder':
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        checkpoint = torch.load(path, map_location=device)
        model = MetricAutoencoder(l2_reg=checkpoint.get('l2_reg', 0.001))
        model.load_state_dict(checkpoint['model_state_dict'])
        model.to(device)
        return model
