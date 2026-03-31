import torch
import random
from collections import Counter
import torch.nn.functional as F
import numpy as np
import matplotlib.pyplot as plt
from torch.nn.utils.rnn import pack_padded_sequence
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
import csv
import os

HIDDEN_SIZE = 128
BATCH_SIZE = 256
N_LAYER = 2
N_EPOCHES = 40
N_CHARS = 128
USE_GPU = True

# 全局固定16类（与CSV严格对齐）
COUNTRY_LIST = [
    "American",
    "Arabic",
    "British",
    "Chinese",
    "Dutch",
    "French",
    "German",
    "Indian",
    "Italian",
    "Japanese",
    "Korean",
    "Polish",
    "Portuguese",
    "Russian",
    "Spanish",
    "Vietnamese",
]
COUNTRY_DICT = {name: idx for idx, name in enumerate(COUNTRY_LIST)}
N_COUNTRIES = len(COUNTRY_LIST)


class NameDataset(Dataset):
    def __init__(self, is_train=True):
        base_dir = r"D:\Projects\Python projects\Artificial Intelligence\Machine Learning\Deep Learning\Projects\dataset\name_country_dataset"
        train_path = os.path.join(base_dir, "train_wiki_cleaned.csv")
        test_path = os.path.join(base_dir, "test_wiki_cleaned.csv")
        path = train_path if is_train else test_path

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # 跳过表头
            rows = list(reader)

        # 严格过滤16类
        valid_rows = [
            (row[0], row[1]) for row in rows if len(row) >= 2 and row[1] in COUNTRY_DICT
        ]

        self.names = [r[0] for r in valid_rows]
        self.countries = [r[1] for r in valid_rows]
        self.len = len(self.names)

        # 使用全局固定映射
        self.country_list = COUNTRY_LIST
        self.n_country = N_COUNTRIES
        self.countryDict = COUNTRY_DICT

        print(
            f"{'训练集' if is_train else '测试集'}分布: {dict(Counter(self.countries))}"
        )

    def __getitem__(self, idx):
        # 返回字符串（供make_tensors转为索引）
        return self.names[idx], self.countries[idx]

    def __len__(self):
        return self.len

    def getCountryName(self, idx):
        """支持单索引或列表"""
        if isinstance(idx, int):
            return COUNTRY_LIST[idx]
        return [COUNTRY_LIST[i] for i in idx]


train_data = NameDataset(True)
train_loader = DataLoader(train_data, batch_size=BATCH_SIZE, shuffle=True)
test_data = NameDataset(False)
test_loader = DataLoader(test_data, batch_size=BATCH_SIZE, shuffle=False)


def create_tensor(tensor):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    return tensor.to(device)


class Classifier(torch.nn.Module):
    def __init__(
        self, input_size, hidden_size, output_size, n_layer=1, bidirectional=True
    ):
        super(Classifier, self).__init__()
        self.n_layer = n_layer
        self.hidden_size = hidden_size
        self.directions = 2 if bidirectional else 1

        self.embedding = torch.nn.Embedding(input_size, hidden_size)

        # CNN多分辨率：输出通道72+32+24=128，加上输入128，共256维输入GRU
        self.conv2 = torch.nn.Conv1d(hidden_size, 72, kernel_size=2)
        self.conv3 = torch.nn.Conv1d(hidden_size, 32, kernel_size=3, padding=1)
        self.conv4 = torch.nn.Conv1d(hidden_size, 24, kernel_size=4, padding=1)

        self.cnn_activation = torch.nn.ReLU()
        self.cnn_dropout = torch.nn.Dropout(0.3)

        # GRU输入维度：128(emb) + 72 + 32 + 24 = 256
        self.gru = torch.nn.GRU(
            256,  # HIDDEN_SIZE + 72 + 32 + 24 = 128 + 128 = 256
            hidden_size,
            num_layers=n_layer,
            bidirectional=bidirectional,
            dropout=0.5 if n_layer > 1 else 0,
            batch_first=True,
        )
        self.fc = torch.nn.Linear(self.directions * hidden_size, output_size)

    def _init_hidden(self, batch_size):
        hidden = torch.zeros(
            self.n_layer * self.directions, batch_size, self.hidden_size
        )
        return create_tensor(hidden)

    def forward(self, inputs, seq_lengths):
        batch_size = inputs.size(0)
        hidden = self._init_hidden(batch_size)

        embedding = self.embedding(inputs)  # (B, L, 128)
        cnn_input = embedding.permute(0, 2, 1)  # (B, 128, L)
        max_len = cnn_input.size(2)

        # 并行卷积
        c2 = self.cnn_activation(self.conv2(cnn_input))
        c3 = self.cnn_activation(self.conv3(cnn_input))
        c4 = self.cnn_activation(self.conv4(cnn_input))

        # 补零对齐
        if c2.size(2) < max_len:
            c2 = F.pad(c2, (0, max_len - c2.size(2)))
        if c4.size(2) < max_len:
            c4 = F.pad(c4, (0, max_len - c4.size(2)))

        # 拼接：128 + 72 + 32 + 24 = 256
        cnn_features = torch.cat([cnn_input, c2, c3, c4], dim=1)
        cnn_features = self.cnn_dropout(cnn_features)

        # 转置给GRU：(B, L, 256)
        gru_input = cnn_features.permute(0, 2, 1)

        # Pack & GRU
        gru_input_packed = pack_padded_sequence(
            gru_input, seq_lengths.cpu(), batch_first=True
        )
        outputs, hidden = self.gru(gru_input_packed, hidden)

        # 取最后时刻
        if self.directions == 2:
            hidden_cat = torch.cat([hidden[-1], hidden[-2]], dim=1)
        else:
            hidden_cat = hidden[-1]

        return self.fc(hidden_cat)


def name2list(name):
    arr = [ord(c) for c in name if ord(c) < 128]  # 只保留标准ASCII
    if not arr:  # 如果过滤后为空，至少返回一个空格（ASCII 32）
        arr = [32]
    return arr, len(arr)


def make_tensors(names, countries):
    """
    纯转换函数：字符串标签 -> 数字索引
    """
    sequences_and_lengths = [name2list(name) for name in names]
    name_sequences = [sl[0] for sl in sequences_and_lengths]
    seq_lengths = torch.LongTensor([sl[1] for sl in sequences_and_lengths])

    # 字符串转索引（关键步骤，防止CUDA断言错误）
    target_indices = [COUNTRY_DICT[c] for c in countries]
    target = torch.LongTensor(target_indices)

    # Padding
    max_len = int(seq_lengths.max())
    seq_tensor = torch.zeros(len(name_sequences), max_len).long()
    for idx, (seq, length) in enumerate(zip(name_sequences, seq_lengths)):
        seq_tensor[idx, :length] = torch.LongTensor(seq)

    # 长度降序排序（pack_padded要求）
    seq_lengths, perm_idx = seq_lengths.sort(dim=0, descending=True)
    seq_tensor = seq_tensor[perm_idx]
    target = target[perm_idx]

    return create_tensor(seq_tensor), create_tensor(seq_lengths), create_tensor(target)


def train(epoch):
    classifier.train()
    total_loss = 0.0
    for idx, (name, country_str) in enumerate(train_loader, 1):
        input, length, target = make_tensors(name, country_str)
        output = classifier(input, length)
        loss = criterion(output, target)
        total_loss += loss.item()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if idx % 10 == 0:
            print(
                f"[{idx * len(input)} / {len(train_data)}] loss = {total_loss / (idx * len(input)):.4f}"
            )

    return total_loss


def test():
    classifier.eval()
    correct = 0
    total = len(test_data)
    print("evaluating trained model ...")
    with torch.no_grad():
        for i, (names, country_strs) in enumerate(test_loader, 1):
            inputs, seq_lengths, target = make_tensors(names, country_strs)
            output = classifier(inputs, seq_lengths)
            pred = output.max(dim=1, keepdim=True)[1]
            correct += pred.eq(target.view_as(pred)).sum().item()

    percent = "%.2f" % (100 * correct / total)
    print(f"Test set: Accuracy {correct} / {total} {percent} %")
    return correct / total


def guess(name):
    classifier.eval()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    arr = [ord(c) for c in name]
    name_tensor = torch.LongTensor([arr]).to(device)
    seq_length = torch.LongTensor([len(arr)]).to(device)

    with torch.no_grad():
        output = classifier(name_tensor, seq_length)
        prob = torch.softmax(output, dim=1)
        top3_probs, top3_idx = torch.topk(prob, 3, largest=True, dim=1)

        pred_countries = train_data.getCountryName(top3_idx[0].cpu().tolist())
        results = list(zip(pred_countries, top3_probs[0].cpu().numpy().tolist()))

        print(f"{name} ->")
        for country, p in results:
            print(f"  {country}: {100 * p:.2f} %")


if __name__ == "__main__":
    SAVE_PATH = "best_name_classifier.pth"  # 模型保存路径
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    # 初始化模型
    classifier = Classifier(N_CHARS, HIDDEN_SIZE, N_COUNTRIES, N_LAYER)
    classifier.to(device)

    criterion = torch.nn.CrossEntropyLoss(label_smoothing=0.15)
    optimizer = torch.optim.Adam(classifier.parameters(), lr=0.001)

    # 【关键1】加载已存在最佳准确率（如果之前有保存）
    best_acc = 0.0
    start_epoch = 1

    if os.path.exists(SAVE_PATH):
        print(f"发现已有模型: {SAVE_PATH}，正在加载...")
        checkpoint = torch.load(SAVE_PATH, map_location=device)

        # 恢复模型参数
        classifier.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

        # 恢复最佳准确率和上次训练的epoch
        best_acc = checkpoint.get("best_acc", 0.0)
        start_epoch = checkpoint.get("epoch", 0) + 1

    print(
        f"已恢复训练状态 | 上次最佳准确率: {best_acc:.4f} | 从Epoch {start_epoch}继续"
    )

    # 【关键2】训练循环中的条件保存逻辑
    acclist = []

    for epoch in range(start_epoch, N_EPOCHES + 1):
        print(f"\n{'=' * 50}")
        print(f"Epoch {epoch}/{N_EPOCHES} | 当前最佳: {best_acc:.4f}")
        print(f"{'=' * 50}")

        train(epoch)
        acc = test()
        acclist.append(acc)

        # 【核心逻辑】只有当准确率提升时才保存
        if acc > best_acc:
            best_acc = acc
            checkpoint = {
                "epoch": epoch,
                "model_state_dict": classifier.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "best_acc": best_acc,
                "hidden_size": HIDDEN_SIZE,
                "n_layer": N_LAYER,
                "n_chars": N_CHARS,
                "n_countries": N_COUNTRIES,
                "country_list": COUNTRY_LIST,  # 【关键】必须保存，确保预测时类别映射一致
                "country_dict": COUNTRY_DICT,  # 【关键】必须保存
                "random_state": random.getstate(),  # 可选：保证完全可复现
                "torch_rng_state": torch.get_rng_state(),
                "model_architecture": "CNN-GRU-Classifier",  # 版本标识
            }

            torch.save(checkpoint, SAVE_PATH)
            print(f" 准确率提升至 {best_acc:.4f}，模型已保存至: {SAVE_PATH}")
        else:
            print(f" 准确率 {acc:.4f} 未超过最佳 {best_acc:.4f}，跳过保存")

    print(f"\n训练完成！最终最佳准确率: {best_acc:.4f}")
