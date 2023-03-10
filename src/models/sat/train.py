import wandb
import torch
import os
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
from model import SatGNN, HGT, HGTMeta
from dataset import SatDataset
from torch_geometric.loader import DataLoader
import multiprocessing
multiprocessing.set_start_method('spawn', force=True)


def train_model(model, train_loader, test_loader, optimizer, criterion, num_epochs):
    train_losses, test_losses, train_accs, test_accs = [], [], [], []
    for epoch in range(1, num_epochs):
        train_acc, train_loss = train_one_epoch(model, optimizer, criterion, train_loader)
        train_losses.append(train_loss)
        train_accs.append(train_acc)
        test_acc, test_loss = test_model(model, test_loader, criterion)
        test_losses.append(test_loss)
        test_accs.append(test_acc)

        print(
            f'Epoch: {epoch:03d}, Train loss: {train_loss:.4f}, Train acc: {train_acc:.4f}')
        print(
            f'Epoch: {epoch:03d}, Test loss: {test_loss:.4f}, Test acc: {test_acc:.4f}')

    return train_losses, test_losses, train_accs, test_accs

def train_one_epoch(model, optimizer, criterion, train_loader):
    model.train()
    right_classification = 0
    total_examples = 0
    total_loss = 0
    for data in train_loader:
        data = data.to(device="cuda:0")
        optimizer.zero_grad()
        out = model(data.x_dict, data.edge_index_dict, data.batch_dict)
        loss = criterion(out, data["variable"].y)
        loss.backward()
        optimizer.step()
        right_classification += sum(out.argmax(dim=1)
                                    == data["variable"].y.argmax(dim=1)).item()
        total_examples += len(data)
        total_loss += loss.item()
    
    train_acc, train_loss = right_classification/total_examples, float(total_loss)

    train_metrics = {
        "train/global_acc": train_acc,
        "train/acc_sat": train_acc,
        "train/acc_unsat": train_acc,
        "train/loss": train_loss
    }
    wandb.log(train_metrics)

    return train_acc, train_loss

def test_model(model, loader, criterion):
    model.eval()
    right_classification = 0
    total_examples = 0
    total_loss = 0

    for data in loader:  # Iterate in batches over the training/test dataset.
        data = data.to(device="cuda:0")
        with torch.no_grad():
            out = model(data.x_dict, data.edge_index_dict, data.batch_dict)
            loss = criterion(out, data["variable"].y)
            right_classification += sum(out.argmax(dim=1)
                                        == data["variable"].y.argmax(dim=1)).item()
            total_examples += len(data)
            total_loss += loss.item()
    
    test_acc, test_loss = right_classification/total_examples, float(total_loss)
    test_metrics = {
        "test/acc": test_acc,
        "test/loss": test_loss
    }
    wandb.log(test_metrics)

    return test_acc, test_loss

if __name__ == "__main__":
    test_path = r"C:\Users\leobo\Desktop\??cole\Poly\Recherche\Generic-Graph-Representation\Graph-Representation\src\models\sat\data"

    hidden_units = [128, 256]
    learning_rates = [0.001, 0.005, 0.1]
    num_layers = [4, 7]
    dropout = 0.3
    num_epochs = 100
    batch_size = 512
    num_heads = 2
    device = "cuda:0"

    dataset = SatDataset(root=test_path, graph_type="refactored")
    train_dataset = dataset[:18000]
    test_dataset = dataset[18000:]

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=False, num_workers=4)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=4)
    criterion = torch.nn.BCELoss()

    for num_hidden_units in hidden_units:
        for lr in learning_rates:
            for layers in num_layers:
                wandb.init(
                    project="generic-graph-rep-sat",
                    name=f"h={num_hidden_units}-l={layers}-lr={lr}-dr={dropout}-refactored",
                    config={
                        "epochs": num_epochs,
                        "batch_size": batch_size,
                        "num_layers": layers,
                        "learning_rate": lr,
                        "hidden_units": num_hidden_units,
                        "dropout": dropout,
                        "num_heads": num_heads
                    }
                )
                config = wandb.config

                if dataset.graph_type == "refactored":
                    model = HGTMeta(num_hidden_units, 2, num_heads, layers, train_dataset[0], dropout_prob=dropout)
                else:
                    model = HGT(num_hidden_units, 2, num_heads, layers, train_dataset[0], dropout_prob=dropout)
                model = model.to(device)
                optimizer = torch.optim.Adam(model.parameters(), lr=lr)
                train_losses, test_losses, train_accs, test_accs = train_model(model, train_loader, test_loader, optimizer, criterion, num_epochs)
    
    wandb.finish()