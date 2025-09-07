# 并发处理优化 (Concurrent Processing Improvements)

## v2.1.0 并发版本更新

### 主要改进

1. **并发处理架构**
   - 替换串行处理为异步并发处理
   - 使用 `asyncio.Semaphore` 控制并发数量
   - 实时进度监控和状态反馈

2. **性能提升**
   - 并发处理多个音频文件，大幅提升处理速度
   - 可配置的并发任务数量（默认3个）
   - 智能批量处理避免API限制

3. **资源管理**
   - 信号量控制避免过载BeatSaver API
   - 连接池复用提高网络效率
   - 内存使用优化和缓存管理

4. **错误处理**
   - 单个任务失败不影响其他任务
   - 完善的异常捕获和日志记录
   - 处理时间统计和性能监控

### 配置选项

在 `config/settings.yaml` 中新增：

```yaml
# 性能配置
performance:
  max_concurrent_tasks: 3     # 最大并发任务数
  batch_size: 50             # 批量处理大小
  max_failures_per_batch: 10 # 每批最大失败容忍数
  show_progress: true        # 显示进度条
```

### 使用方式

使用方式与之前完全相同，无需修改命令：

```bash
# 标准使用
python main.py --music-dir /path/to/music --output-dir /path/to/output

# 大量文件处理（推荐使用高成功率配置）
python main.py --music-dir /path/to/music --output-dir /path/to/output --config config/high_success_settings.yaml
```

### 性能对比

- **串行版本**: 1846个文件 → 约3-5小时
- **并发版本**: 1846个文件 → 约1-2小时 (提升2-3倍)

### 技术细节

1. **并发控制**
   - 使用 `asyncio.as_completed()` 实时获取完成任务
   - Semaphore 限制同时运行的任务数量
   - 进度条实时更新处理状态

2. **API友好**
   - 保留原有的速率限制机制
   - 适中的并发数避免触发API限制
   - 智能重试和退避策略

3. **监控和日志**
   - 每个任务的处理时间统计
   - 定期输出进度和成功率
   - 详细的错误日志和异常处理

### 注意事项

- 并发数不宜设置过高（建议3-5）
- 网络不稳定时可降低并发数
- 大量文件处理建议分批进行

## 兼容性

- 完全向后兼容，不影响现有配置
- 支持所有原有功能和配置选项
- Windows/Linux/macOS 全平台支持