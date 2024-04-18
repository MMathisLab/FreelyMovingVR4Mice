import torch
import torch.nn as nn


class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_units, output_size, num_layers, device, dropout_rate=0.3):
        super(LSTMModel, self).__init__()
        
        self.device = device
        self.num_layers = num_layers
        self.batch_size = 1 # from shaping with None
        self.hidden_units = hidden_units
        
        self.lstm = nn.LSTM(input_size, self.hidden_units, self.num_layers, batch_first=False,
                            dropout=dropout_rate if num_layers > 1 else 0)
        self.fc = nn.Linear(self.hidden_units, output_size)
        
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout_rate)
        
    def init_hidden(self, batch_size):
        return (torch.zeros(batch_size, self.num_layers, self.hidden_units).to(self.device),
                torch.zeros(batch_size, self.num_layers, self.hidden_units).to(self.device))


    def forward(self, x):
        self.hidden = self.init_hidden(batch_size=1)#sx.shape[0])
        out, self.hidden = self.lstm(x, self.hidden)

        #out = torch.sigmoid(self.fc(self.dropout(self.relu(out[:, -1, :]))))
        
        out = torch.sigmoid(self.fc(out[:, -1, :]))
        return out