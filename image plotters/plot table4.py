import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns
from openpyxl import Workbook
from openpyxl.styles import Border, Side, PatternFill, Font, Alignment

# 指定保存路径
save_path1 = 'C:/Users/25610/Desktop/online3/savenewPDOCcylindrical'
save_path2 = 'C:/Users/25610/Desktop/online3/savenewPDOCcylindrical+'
save_path3 = 'C:/Users/25610/Desktop/online3/savenewPDOCcylindrical++'
save_path4 = 'C:/Users/25610/Desktop/online3/savenewPDOCcylindrical++Bilinear'  # 新增路径

# 初始化
std_devs1 = {}
std_devs2 = {}
std_devs3 = {}
std_devs4 = {}  # 新增字典

def calculate_std(y_pred, Y_test):
    y_pred_flat = y_pred.flatten()
    Y_test_flat = Y_test.flatten()
    
    # 排除真实值为0的情况
    non_zero_mask = Y_test_flat != 0
    y_pred_flat = y_pred_flat[non_zero_mask]
    Y_test_flat = Y_test_flat[non_zero_mask]
    
    diff = y_pred_flat - Y_test_flat
    std_dev = np.std(diff)
    return std_dev

def process_path(save_path, std_devs):
    for field in range(0, 151):
        field_str = f'{field:02d}'  # 格式化为两位数
        std_devs_for_field = []
        
        for i in range(10):  # 假设每组最多有10个文件
            predictions_file = f'predictions{field_str}.{i}.npy'
            truth_file = f'truth{field_str}.{i}.npy'
            
            # 检查文件是否存在
            if os.path.exists(os.path.join(save_path, predictions_file)) and os.path.exists(os.path.join(save_path, truth_file)):
                # 加载预测结果和真实值
                y_pred = np.load(os.path.join(save_path, predictions_file))
                Y_test = np.load(os.path.join(save_path, truth_file))
                
                # 计算标准差
                std_dev = calculate_std(y_pred, Y_test)
                std_devs_for_field.append(std_dev)
        
        # 计算平均标准差
        if std_devs_for_field:
            avg_std_dev = np.mean(std_devs_for_field)
            std_devs[field] = (avg_std_dev, np.std(std_devs_for_field))

# 处理四个路径的数据
process_path(save_path1, std_devs1)
process_path(save_path2, std_devs2)
process_path(save_path3, std_devs3)
process_path(save_path4, std_devs4)  # 新增路径处理

# 创建数据表格
fields = sorted(set(std_devs1.keys()).union(std_devs2.keys()).union(std_devs3.keys()).union(std_devs4.keys()))
data = {
    'Field': fields,
    'Cylindrical': [std_devs1[field][0] if field in std_devs1 else None for field in fields],
    'Cylindrical+': [std_devs2[field][0] if field in std_devs2 else None for field in fields],
    'Cylindrical++': [std_devs3[field][0] if field in std_devs3 else None for field in fields],
    'Cylindrical++B': [std_devs4[field][0] if field in std_devs4 else None for field in fields]  # 新增列
}

df = pd.DataFrame(data)
df.set_index('Field', inplace=True)

# 绘制表格图片
fig, ax = plt.subplots(figsize=(12, 8))  # 调整图像尺寸以适应更多数据

# 移除表格边框
ax.axis('off')
ax.axis('tight')

# 渲染表格，使用不同的颜色来突出数据
table = ax.table(cellText=df.values,
                 colLabels=df.columns,
                 rowLabels=df.index,
                 loc='center',
                 cellLoc='center',
                 colColours=['#f2f2f2'] * df.shape[1],  # 列颜色
                 rowColours=['#f2f2f2'] * df.shape[0])  # 行颜色

# 设置字体大小
table.auto_set_font_size(False)
table.set_fontsize(12)

# 调整列宽
table.scale(1.2, 1.2)

# 保存表格为图片
plt.savefig(os.path.join(save_path1, 'std_dev_comparison_table_four_sets.png'), bbox_inches='tight')
plt.show()