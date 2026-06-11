# 真实相机测试指南

## 概述

HiKCamera 项目包含完整的真实相机集成测试套件，用于验证库在实际海康威视工业相机上的功能。这些测试使用 GVCP（GigE Vision Control Protocol）和 GVSP（GigE Vision Streaming Protocol）协议与相机通信。

## 测试架构

### 相机实例管理

为了避免相机独占访问冲突，测试套件采用 **session 级别的相机实例复用**策略：

- **单个相机实例**: 整个测试会话中只创建一个相机实例
- **自动生命周期管理**: 相机在测试会话开始时打开，结束时关闭
- **测试间共享**: 所有测试共享同一个相机实例，避免重复打开/关闭导致的冲突

### 可达性检测

测试前会自动检测相机是否可达，检测方法包括：

1. **GVCP 端口检查** (TCP 3956) - GigE Vision 控制协议标准端口
2. **ICMP Ping** - 作为备选方案

> **注意**: 工业相机使用 GVCP/GVSP 协议，不使用 HTTP（80端口）。

## 运行测试

### 前提条件

1. **硬件要求**:
   - 海康威视 GigE 工业相机
   - 相机已连接到网络并可访问

2. **软件要求**:
   - 已安装 MVS SDK
   - Python 3.12+
   - Poetry 依赖管理

3. **配置相机信息**:

   可以通过环境变量或修改 `tests/conftest.py` 来配置：

   ```python
   # tests/conftest.py
   REAL_CAMERA_IP = "192.168.1.1"      # 相机 IP 地址
   REAL_CAMERA_SN = "DA4860722"        # 相机序列号
   ```

   或使用环境变量：

   ```bash
   export HIKCAMERA_TEST_IP=192.168.1.1
   export HIKCAMERA_TEST_SN=DA4860722
   ```

### 运行命令

```bash
# 运行所有真实相机测试
poetry run pytest tests/ -k "real_camera" -v

# 运行特定测试文件
poetry run pytest tests/test_real_camera_basic.py -v

# 运行特定测试类
poetry run pytest tests/test_real_camera_basic.py::TestRealCameraConnection -v

# 运行特定测试方法
poetry run pytest tests/test_real_camera_basic.py::TestRealCameraConnection::test_connect_by_ip -v

# 显示详细输出
poetry run pytest tests/ -k "real_camera" -v -s

# 生成覆盖率报告
poetry run pytest tests/ -k "real_camera" --cov=hikcamera --cov-report=html

# 快速查看结果摘要
poetry run pytest tests/ -k "real_camera" --tb=line -q
```

### 测试标记

测试使用以下 pytest markers：

- `@pytest.mark.integration`: 标记为集成测试
- `@pytest.mark.hardware`: 标记为需要真实硬件的测试

可以单独运行硬件测试：

```bash
poetry run pytest -m hardware -v
```

## 测试覆盖范围

### 1. 基础连接与枚举 (`test_real_camera_basic.py`)

**TestRealCameraEnumeration**
- ✅ 枚举所有可用相机
- ✅ 仅枚举 GigE 相机
- ✅ 验证设备信息属性

**TestRealCameraConnection**
- ✅ 通过 IP 地址连接
- ✅ 通过序列号连接
- ✅ 独占模式连接 (EXCLUSIVE)
- ✅ 控制模式连接 (CONTROL)
- ✅ 监视模式连接 (MONITOR)
- ✅ 上下文管理器 (`with` 语句)
- ✅ 重复打开错误处理
- ✅ 关闭后重新打开

**TestRealCameraDeviceInfo**
- ✅ 获取相机信息
- ✅ 设备型号名称
- ✅ 设备序列号
- ✅ 图像尺寸

**TestRealCameraGigEPacketSize**
- ✅ 获取最优包大小
- ✅ 获取当前包大小
- ✅ 设置包大小
- ✅ 自动包大小打开
- ✅ 手动包大小打开

**TestRealCameraMulticast**
- ⏭️ 多播模式打开（需要交换机支持 IGMP）

### 2. 参数系统 (`test_real_camera_parameters.py`)

**TestRealCameraParameterTypes**
- ✅ 读取整数参数
- ✅ 读取浮点参数
- ✅ 读取布尔参数
- ✅ 读取枚举参数
- ✅ 读取字符串参数
- ✅ 写入整数参数
- ✅ 写入浮点参数
- ✅ 写入枚举参数
- ✅ 写入布尔参数
- ✅ 执行命令节点

**TestRealCameraParameterValidation**
- ✅ 无效参数值错误处理
- ✅ 错误类型错误处理
- ✅ 不支持参数错误处理

**TestRealCameraCommonParameters**
- ✅ 曝光时间范围
- ✅ 增益值
- ✅ 帧率
- ✅ 像素格式值

**TestRealCameraUserSets**
- ✅ 用户集选择器
- ✅ 用户集保存/加载

**TestRealCameraParameterProxy**
- ✅ 参数代理结构
- ✅ 绑定参数节点获取
- ✅ 绑定参数节点设置
- ✅ 参数节点 repr

**TestRealCameraGetCameraInfo**
- ✅ get_camera_info 返回字典
- ✅ 包含常用参数
- ✅ ParamNode 键访问
- ✅ 传统字符串键访问

### 3. 帧采集 (`test_real_camera_grabbing.py`)

**TestRealCameraPollingMode**
- ✅ 轮询模式取帧
- ✅ 多种输出格式 (MONO8, MONO16, BGR8, RGB8, BGRA8, RGBA8)
- ✅ 帧信息完整性

**TestRealCameraCallbackMode**
- ✅ 回调模式取帧
- ✅ 回调函数接收数据
- ✅ 连续帧稳定性

### 4. 高级功能 (`test_real_camera_advanced.py`)

**TestRealCameraSDKDecode**
- ✅ SDK 解码启用/禁用
- ✅ Bayer 质量设置

**TestRealCameraImageOperations**
- ✅ 图像旋转 (90°, 180°, 270°)
- ✅ 图像翻转 (水平、垂直)

**TestRealCameraEncoding**
- ✅ JPEG 编码
- ✅ PNG 编码
- ✅ BMP 编码

**TestRealCameraConfigManagement**
- ✅ 导出配置
- ✅ 导入配置

### 5. 边界情况 (`test_real_camera_edge_cases.py`)

**TestRealCameraExceptionHandling**
- ✅ 异常回调
- ✅ 设备断开检测

**TestRealCameraLifecycle**
- ✅ 生命周期管理
- ✅ 资源清理

**TestRealCameraTimeoutScenarios**
- ✅ 超时处理
- ✅ 帧超时异常

**TestRealCameraThreadSafety**
- ✅ 线程安全测试

## 测试结果解读

### 状态说明

- ✅ **PASSED**: 测试通过
- ❌ **FAILED**: 测试失败（代码问题）
- ⏭️ **SKIPPED**: 测试跳过（相机不可用或不支持该功能）
- ⚠️ **ERROR**: 测试错误（通常是资源问题，如相机被占用）

### 常见问题

#### 1. 相机不可达

```
SKIPPED: Real camera at 192.168.1.1 is not available
```

**解决方案**:
- 检查相机电源和网络连接
- 确认 IP 地址正确
- 使用 `ping 192.168.1.1` 测试网络连通性
- 检查防火墙设置

#### 2. 相机被占用

```
ERROR: CameraConnectionError: Failed to open camera (access_mode=EXCLUSIVE)
```

**解决方案**:
- 等待几秒后重试（其他测试可能刚释放相机）
- 确保没有其他程序（如 MVS Client）连接相机
- 重启相机

#### 3. 参数不支持

```
SKIPPED: ParameterNotSupportedError
```

**说明**: 某些参数不是所有相机型号都支持，这是正常现象。

#### 4. 多播测试跳过

```
SKIPPED: Multicast not supported
```

**说明**: 多播需要网络交换机支持 IGMP snooping，普通环境可能不支持。

## 测试最佳实践

### 1. 不要手动关闭相机

测试中使用的是 session 级别的相机实例，由 fixture 统一管理生命周期。不要在测试中调用 `cam.close()`。

### 2. 避免长时间占用相机

如果测试需要停止取帧，确保在测试结束前调用 `stop_grabbing()`。

### 3. 恢复参数值

如果测试修改了相机参数，尽量在测试结束时恢复原值：

```python
def test_parameter(self, real_camera):
    original_value = real_camera.params.AcquisitionControl.ExposureTime.get()
    try:
        real_camera.params.AcquisitionControl.ExposureTime.set(5000.0)
        # ... 测试代码 ...
    finally:
        real_camera.params.AcquisitionControl.ExposureTime.set(original_value)
```

### 4. 使用适当的超时

取帧测试应设置合理的超时时间，避免测试挂起：

```python
frame = real_camera.get_frame(timeout_ms=1000)
```

## CI/CD 集成

在持续集成环境中，可以配置为仅在特定条件下运行硬件测试：

```yaml
# .github/workflows/ci.yml
- name: Run hardware tests
  if: github.event_name == 'schedule' || contains(github.event.inputs.run-hardware-tests, 'true')
  run: poetry run pytest tests/ -k "real_camera" -v
```

或者将硬件测试标记为可选：

```bash
# 默认跳过硬件测试
poetry run pytest tests/ -v

# 显式运行时才执行硬件测试
poetry run pytest tests/ -m hardware -v
```

## 故障排除

### 诊断相机连接

```python
from tests.conftest import is_camera_reachable

# 检查相机是否可达
print("Camera reachable:", is_camera_reachable("192.168.1.1"))
```

### 查看相机信息

```python
from hikcamera import HikCamera

cameras = HikCamera.enumerate()
for cam_info in cameras:
    print(f"Model: {cam_info.model_name}")
    print(f"SN: {cam_info.serial_number}")
    print(f"IP: {cam_info.ip}")
```

### 调试测试

```bash
# 显示打印输出
poetry run pytest tests/ -k "real_camera" -v -s

# 只显示失败的测试
poetry run pytest tests/ -k "real_camera" --tb=short

# 进入调试模式
poetry run pytest tests/ -k "real_camera" --pdb
```

## 维护建议

1. **定期验证**: 在有相机可用的环境中定期运行测试
2. **参数更新**: 如果相机型号变更，可能需要调整某些参数范围断言
3. **新特性覆盖**: 添加新功能时，考虑添加对应的真实相机测试
4. **性能监控**: 可以添加性能基准测试来监控相机操作的性能变化

## 相关文档

- [HiKCamera README](../README.md)
- [HiKCamera 中文说明](../README_zh.md)
- [MVS SDK 文档](https://www.hikrobotics.com/cn/machinevision/service/download/?module=0)

## 技术支持

如有问题，请提交 Issue 或联系维护者。
