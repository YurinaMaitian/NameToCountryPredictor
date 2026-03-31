import torch
import torch.nn.functional as F
from torch.nn.utils.rnn import pack_padded_sequence
import os


# the same structrue to the train
class Classifier(torch.nn.Module):
    def __init__(
        self, input_size, hidden_size, output_size, n_layer=1, bidirectional=True
    ):
        super(Classifier, self).__init__()
        self.n_layer = n_layer
        self.hidden_size = hidden_size
        self.directions = 2 if bidirectional else 1

        self.embedding = torch.nn.Embedding(input_size, hidden_size)
        self.conv2 = torch.nn.Conv1d(hidden_size, 72, kernel_size=2)
        self.conv3 = torch.nn.Conv1d(hidden_size, 32, kernel_size=3, padding=1)
        self.conv4 = torch.nn.Conv1d(hidden_size, 24, kernel_size=4, padding=1)
        self.cnn_activation = torch.nn.ReLU()
        self.cnn_dropout = torch.nn.Dropout(0.3)
        self.gru = torch.nn.GRU(
            256,
            hidden_size,
            num_layers=n_layer,
            bidirectional=bidirectional,
            dropout=0.5 if n_layer > 1 else 0,
            batch_first=True,
        )
        self.fc = torch.nn.Linear(self.directions * hidden_size, output_size)

    def _init_hidden(self, batch_size, device):
        hidden = torch.zeros(
            self.n_layer * self.directions, batch_size, self.hidden_size
        )
        return hidden.to(device)

    def forward(self, inputs, seq_lengths):
        batch_size = inputs.size(0)
        device = inputs.device
        hidden = self._init_hidden(batch_size, device)

        embedding = self.embedding(inputs)
        cnn_input = embedding.permute(0, 2, 1)
        max_len = cnn_input.size(2)

        c2 = self.cnn_activation(self.conv2(cnn_input))
        c3 = self.cnn_activation(self.conv3(cnn_input))
        c4 = self.cnn_activation(self.conv4(cnn_input))

        if c2.size(2) < max_len:
            c2 = F.pad(c2, (0, max_len - c2.size(2)))
        if c4.size(2) < max_len:
            c4 = F.pad(c4, (0, max_len - c4.size(2)))

        cnn_features = torch.cat([cnn_input, c2, c3, c4], dim=1)
        cnn_features = self.cnn_dropout(cnn_features)
        gru_input = cnn_features.permute(0, 2, 1)

        gru_input_packed = pack_padded_sequence(
            gru_input, seq_lengths.cpu(), batch_first=True
        )
        outputs, hidden = self.gru(gru_input_packed, hidden)

        if self.directions == 2:
            hidden_cat = torch.cat([hidden[-1], hidden[-2]], dim=1)
        else:
            hidden_cat = hidden[-1]

        return self.fc(hidden_cat)


class NamePredictor:
    def __init__(self, model_path="best_name_classifier.pth"):
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f" 模型文件不存在: {model_path}\n请先运行训练文件生成模型。"
            )

        # 加载检查点
        print(f"正在加载模型: {model_path}...")
        checkpoint = torch.load(
            model_path, map_location=self.device, weights_only=False
        )

        # 恢复配置
        self.hidden_size = checkpoint["hidden_size"]
        self.n_layer = checkpoint["n_layer"]
        self.n_countries = checkpoint["n_countries"]
        self.country_list = checkpoint["country_list"]
        self.best_acc = checkpoint.get("best_acc", 0.0)
        self.trained_epochs = checkpoint.get("epoch", 0)

        # 初始化并加载参数
        self.model = Classifier(128, self.hidden_size, self.n_countries, self.n_layer)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()  # 关闭 Dropout

        print(
            f" 加载成功 | 训练轮次: {self.trained_epochs} | 最佳准确率: {self.best_acc:.2%}"
        )
        print(f" 支持 {self.n_countries} 个国家预测")

    def name2list(self, name):
        """与训练文件完全一致的编码逻辑"""
        arr = [ord(c) for c in name if ord(c) < 128]
        if not arr:
            arr = [32]  # 空格兜底
        return arr, len(arr)

    def get_country_name(self, idx):
        """支持单索引或列表"""
        if isinstance(idx, int):
            return self.country_list[idx]
        return [self.country_list[i] for i in idx]

    def guess(self, name, top_k=3):
        """
        与训练文件一致的预测函数
        返回: list of (country, probability)
        """
        # 预处理
        arr, length = self.name2list(name)
        name_tensor = torch.LongTensor([arr]).to(self.device)
        seq_length = torch.LongTensor([length]).to(self.device)

        with torch.no_grad():
            output = self.model(name_tensor, seq_length)
            prob = torch.softmax(output, dim=1)
            top_probs, top_idx = torch.topk(prob, top_k, largest=True, dim=1)

            pred_countries = self.get_country_name(top_idx[0].cpu().tolist())
            results = list(zip(pred_countries, top_probs[0].cpu().numpy().tolist()))

            # 格式化输出（与原文件风格一致）
            print(f"{name} ->")
            for country, p in results:
                print(f"  {country}: {100 * p:.2f} %")

            return results


if __name__ == "__main__":
    # 初始化（自动加载同级目录下的模型文件）
    try:
        predictor = NamePredictor("best_name_classifier.pth")
    except FileNotFoundError as e:
        print(e)
        exit(1)

    print("\n" + "=" * 50)
    print("人名-国籍预测系统")
    print("输入人名进行预测，输入 'quit' 或 'exit' 退出")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n>>> 请输入人名: ").strip()

            # 退出条件
            if user_input.lower() in ["quit", "exit", "q", ""]:
                break

            # 执行预测
            predictor.guess(user_input)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"预测出错: {e}")
