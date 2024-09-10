import numpy as np
import glob
import os
import re
import tifffile as tiff
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Input
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.layers import Conv2D
import tensorflow as tf

# 数据文件夹路径
folder_path = 'C:/Users/25610/Desktop/Online/Gauss_S1.00_NL0.30_B0.50'
# 保存路径
save_path = 'C:/Users/25610/Desktop/online3/save3'
os.makedirs(save_path, exist_ok=True)

# 自然排序函数
def natural_sort_key(s):
    sub_strings = re.split(r'(\d+)', s)
    sub_strings = [int(c) if c.isdigit() else c for c in sub_strings]
    return sub_strings

# 获取图像路径
emcal_list = sorted(glob.glob(os.path.join(folder_path, 'emcal_*')), key=natural_sort_key)
hcal_list = sorted(glob.glob(os.path.join(folder_path, 'hcal_*')), key=natural_sort_key)
trkn_list = sorted(glob.glob(os.path.join(folder_path, 'trkn_*')), key=natural_sort_key)
trkp_list = sorted(glob.glob(os.path.join(folder_path, 'trkp_*')), key=natural_sort_key)
truth_list = sorted(glob.glob(os.path.join(folder_path, 'truth_*')), key=natural_sort_key)

# 读取图像数据
def load_images(file_list):
    images = [tiff.imread(p) for p in file_list]
    return np.array(images)

emcal_data = load_images(emcal_list)
hcal_data = load_images(hcal_list)
trkn_data = load_images(trkn_list)
trkp_data = load_images(trkp_list)
truth_data = load_images(truth_list)

# 改进的极坐标转换函数
def cartesian_to_polar(image):
    """
    使用双线性插值将图像从笛卡尔坐标转换为极坐标。
    """
    height, width = image.shape
    center_x, center_y = width // 2, height // 2
    max_radius = np.sqrt(center_x**2 + center_y**2)

    # 创建空的极坐标图像
    polar_image = np.zeros_like(image)

    # 创建极坐标的r和theta网格
    theta, radius = np.meshgrid(np.linspace(0, 2 * np.pi, width), np.linspace(0, max_radius, height))

    # 计算笛卡尔坐标
    x = radius * np.cos(theta) + center_x
    y = radius * np.sin(theta) + center_y

    # 双线性插值
    x0 = np.floor(x).astype(int)
    x1 = x0 + 1
    y0 = np.floor(y).astype(int)
    y1 = y0 + 1

    x0 = np.clip(x0, 0, width - 1)
    x1 = np.clip(x1, 0, width - 1)
    y0 = np.clip(y0, 0, height - 1)
    y1 = np.clip(y1, 0, height - 1)

    Ia = image[y0, x0]
    Ib = image[y1, x0]
    Ic = image[y0, x1]
    Id = image[y1, x1]

    wa = (x1 - x) * (y1 - y)
    wb = (x1 - x) * (y - y0)
    wc = (x - x0) * (y1 - y)
    wd = (x - x0) * (y - y0)

    polar_image = wa * Ia + wb * Ib + wc * Ic + wd * Id

    return polar_image

# 将X中的每个图像转换为极坐标
X = np.stack([emcal_data, hcal_data, trkn_data, trkp_data], axis=-1)
Y = truth_data

for i in range(X.shape[0]):
    for j in range(X.shape[-1]):
        X[i, :, :, j] = cartesian_to_polar(X[i, :, :, j])

for i in range(Y.shape[0]):
    Y[i, :, :] = cartesian_to_polar(Y[i, :, :])

# 数据归一化
scalers_X = [MinMaxScaler() for _ in range(X.shape[-1])]
scaler_Y = MinMaxScaler()

for i in range(X.shape[-1]):
    X_channel = X[..., i].reshape(-1, 1)
    scalers_X[i].fit(X_channel)
    X[..., i] = scalers_X[i].transform(X_channel).reshape(X[..., i].shape)

Y = Y.reshape(-1, 1)
scaler_Y.fit(Y)
Y = scaler_Y.transform(Y)
Y = Y.reshape(-1, 56, 56, 1)  # 确保 Y 的形状为 (样本数, 高度, 宽度, 通道数)

# 检查 X 和 Y 的形状
print("Number of samples in X:", X.shape[0])
print("Number of samples in Y:", Y.shape[0])

# 划分数据集
X_train, X_temp, Y_train, Y_temp = train_test_split(X, Y, test_size=0.3, random_state=42)
X_val, X_test, Y_val, Y_test = train_test_split(X_temp, Y_temp, test_size=0.33, random_state=42)

# 定义扇形卷积层
class FanShapeConv2D(tf.keras.layers.Layer):
    def __init__(self, filters, kernel_size, **kwargs):
        super(FanShapeConv2D, self).__init__(**kwargs)
        self.filters = filters
        self.kernel_size = kernel_size
        self.padding = 'SAME'

    def build(self, input_shape):
        kernel_height, kernel_width = self.kernel_size
        self.kernel = self.add_weight(
            shape=(kernel_height, kernel_width, input_shape[-1], self.filters),
            initializer='glorot_uniform',
            trainable=True
        )
        self.fan_mask = self.create_fan_mask(kernel_height, kernel_width)

    def create_fan_mask(self, height, width):
        center_x, center_y = width // 2, height // 2
        y, x = np.indices((height, width))
        r = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        theta = np.arctan2(y - center_y, x - center_x)
        fan_mask = (r <= (min(center_x, center_y) - 1)) & (np.abs(theta) <= np.pi / 4)
        fan_mask = fan_mask.astype(np.float32)
        return tf.constant(fan_mask, dtype=tf.float32)

    def call(self, inputs):
        kernel_height, kernel_width = self.kernel_size
        masked_kernel = self.kernel * tf.reshape(self.fan_mask, (kernel_height, kernel_width, -1, 1))
        patches = tf.image.extract_patches(
            images=inputs,
            sizes=[1, kernel_height, kernel_width, 1],
            strides=[1, 1, 1, 1],
            rates=[1, 1, 1, 1],
            padding=self.padding
        )
        patches_shape = tf.shape(patches)
        num_patches = patches_shape[1] * patches_shape[2]
        patch_size = kernel_height * kernel_width * tf.shape(inputs)[-1]
        patches = tf.reshape(patches, (-1, num_patches, patch_size))
        conv_out = tf.matmul(patches, tf.reshape(masked_kernel, (-1, self.filters)))
        conv_out = tf.reshape(conv_out, (tf.shape(inputs)[0], tf.shape(inputs)[1], tf.shape(inputs)[2], self.filters))
        return conv_out

# 定义模型
model = Sequential([
    Input(shape=(56, 56, 4)),
    Conv2D(32, (3, 3), activation='relu', padding='same'),
    Conv2D(32, (3, 3), activation='relu', padding='same'),
    FanShapeConv2D(filters=64, kernel_size=(5, 5)),
    Conv2D(32, (3, 3), activation='relu', padding='same'),
    Conv2D(1, (1, 1), activation='linear', padding='same'),
])

# 编译模型
model.compile(optimizer=Adam(learning_rate=0.001), loss='mean_squared_error')

# 打印模型结构
model.summary()

# 训练模型
history = model.fit(X_train, Y_train, epochs=100, batch_size=32, validation_data=(X_val, Y_val))

# 保存模型
model.save('my_model1.keras')

# 使用测试集进行测试
y_pred = model.predict(X_test)

# 保存预测结果和真实值
np.save(os.path.join(save_path, 'predictions.npy'), y_pred)
np.save(os.path.join(save_path, 'truth.npy'), Y_test)

print("模型训练和保存成功！")
