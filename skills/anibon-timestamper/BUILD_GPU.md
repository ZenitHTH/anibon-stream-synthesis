# Build whisper.cpp with GPU Acceleration

Supported backends: **CUDA** (NVIDIA), **HIP** (AMD ROCm), **Vulkan** (cross-platform), **Metal** (Apple).

## 1 Prerequisites

### All platforms
- Git, CMake ≥3.10, C++ compiler
- Python 3 (for model conversion scripts)

### NVIDIA — CUDA
- CUDA Toolkit ≥11.x (https://developer.nvidia.com/cuda-downloads)
- `nvcc` in PATH
- GPU: any CUDA-capable card (compute capability ≥5.0)

### AMD — ROCm (Linux only)
- ROCm ≥5.x (https://rocm.docs.amd.com)
- `hipcc`, `rocblas`, `hipblas`, `perl`
- GPU: RX 5000+ (gfx1010+), Radeon VII (gfx906), Instinct
- Works on Linux only. Windows users → use **Vulkan** backend instead.

### AMD — Vulkan (Windows/Linux)
- Vulkan SDK ≥1.3 (https://vulkan.lunarg.com)
- GPU: any Vulkan 1.3 capable card (RX 6000/7000, NVIDIA, Intel ARC)
- `glslc` in PATH (shipped with Vulkan SDK)

### Apple — Metal
- macOS ≥13, Xcode ≥15, Command Line Tools
- Apple Silicon (M1/M2/M3/M4) or AMD GPU

## 2 Clone

```bash
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
```

## 3 Build

### NVIDIA CUDA

```bash
cmake -B build -DGGML_CUDA=ON
cmake --build build -j --config Release
```

| Option | Default | Description |
|--------|---------|-------------|
| `GGML_CUDA_FORCE_CUBLAS` | OFF | Force cuBLAS over custom kernels |
| `GGML_CUDA_FORCE_MMQ` | OFF | Force matrix multiplication kernels |
| `CUDA_ARCHITECTURES` | auto | e.g. `"89;90"` for RTX 4090 |

### AMD HIP (Linux)

```bash
cmake -B build -G Ninja \
  -DGGML_HIP=ON \
  -DCMAKE_C_COMPILER=clang \
  -DCMAKE_CXX_COMPILER=hipcc \
  -DGPU_TARGETS="gfx1030;gfx1100" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build -j --config Release
```

| Option | Default | Description |
|--------|---------|-------------|
| `GPU_TARGETS` | all | e.g. `gfx1030` (RX 6800), `gfx1100` (RX 7600) |
| `GGML_HIP_GRAPHS` | ON | Enable HIP graph capture |
| `GGML_HIP_RCCL` | OFF | ROCm Collective Communications Library |

Find your GPU arch: `rocminfo | grep gfx`

### AMD HIP (Windows — NOT recommended)

ROCm on Windows has known incompatibilities with MSVC STL headers (VS 2026+).  
Use **Vulkan** backend instead — it works on RX 6000/7000 with identical performance.

### Vulkan (Windows/Linux) — RECOMMENDED for AMD on Windows

```bash
cmake -B build -G Ninja -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j --config Release
```

| Option | Default | Description |
|--------|---------|-------------|
| `GGML_VULKAN_CHECK_RESULTS` | OFF | Validate Vulkan results against CPU |
| `GGML_VULKAN_DEBUG` | OFF | Enable debug output |
| `GGML_VULKAN_VALIDATE` | OFF | Enable Vulkan validation layers |

Set `VULKAN_SDK` environment variable if CMake cannot auto-detect.

### Apple Metal

```bash
cmake -B build -G Ninja -DGGML_METAL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j --config Release
```

| Option | Default | Description |
|--------|---------|-------------|
| `GGML_METAL_EMBED_LIBRARY` | ON | Embed shaders in binary |

## 4 Download a Model

Multilingual models (support all languages including Thai):

```bash
# Tiny (fast, low accuracy)
models/download-ggml-model.sh tiny

# Small (good balance)
models/download-ggml-model.sh small

# Medium (recommended for 8 GB VRAM)
models/download-ggml-model.sh medium

# Large v3 Turbo (best quality, ~1.6 GB → fits 8 GB VRAM)
models/download-ggml-model.sh large-v3-turbo

# Quantized version (even smaller, ~800 MB)
models/download-ggml-model.sh large-v3-turbo-q5_0
```

English-only models: `base.en`, `small.en`, `medium.en`.  
Quantized variants: `-q5_0`, `-q8_0` suffix.

### Model VRAM requirements (approximate)

| Model | Size | VRAM (fp16) |
|-------|------|-------------|
| tiny | 75 MB | ~1 GB |
| base | 150 MB | ~2 GB |
| small | 500 MB | ~3 GB |
| medium | 1.5 GB | ~5 GB |
| large-v3 | 3 GB | ~8 GB |
| large-v3-turbo | 1.5 GB | ~5 GB |

## 5 Run

```bash
# English transcription
build/bin/whisper-cli -m ggml-large-v3-turbo.bin -f audio.wav

# Thai transcription
build/bin/whisper-cli -m ggml-large-v3-turbo.bin -l th -f audio.wav

# With timestamps, 8 threads
build/bin/whisper-cli -m ggml-large-v3-turbo.bin -l th -t 8 -f audio.wav

# Output as SRT subtitles
build/bin/whisper-cli -m ggml-large-v3-turbo.bin -l th --output-srt -f audio.wav
```

### Verify GPU is used

Look for these lines in the output:

- **CUDA**: `whisper_backend_init_gpu: using CUDA0 backend`
- **HIP**:  `whisper_backend_init_gpu: using HIP0 backend`
- **Vulkan**: `whisper_backend_init_gpu: using Vulkan0 backend`  
  Also: `ggml_vulkan: 0 = AMD Radeon RX 7600 ...`
- **Metal**: `whisper_backend_init_gpu: using Metal backend`

If you see `no GPU found`, GPU is not working.

### Disable GPU (force CPU fallback)

```bash
build/bin/whisper-cli --no-gpu -m model.bin -f audio.wav
```

## 6 Troubleshooting

### "use of undeclared identifier '__builtin_verbose_trap'"

ROCm clang + MSVC 2026+ STL incompatibility.  
**Fix**: Use Vulkan backend instead (`-DGGML_VULKAN=ON`).

### "no GPU found"

- Vulkan: verify `VULKAN_SDK` env var is set and `glslc` is in PATH
- CUDA: run `nvcc --version` and check `nvidia-smi`
- HIP: run `hipconfig --full` to verify ROCm installation

### Out of memory

Use a smaller model or quantized variant:
```bash
models/download-ggml-model.sh large-v3-turbo-q5_0
```

### Slow performance on Vulkan

Ensure you have the latest GPU drivers installed:
- **AMD**: Adrenalin Edition (Windows), ROCm or amdgpu (Linux)
- **NVIDIA**: Game Ready or Studio Driver
- **Intel**: ARC Graphics driver

### "glslc not found"

Install Vulkan SDK and add `Bin/` to PATH:
```bash
export PATH="/VulkanSDK/1.4.350.0/Bin:$PATH"
```

## Platform Comparison

| Backend | Windows | Linux | macOS | Recommended for |
|---------|---------|-------|-------|-----------------|
| CUDA | ✅ | ✅ | ❌ | NVIDIA GPUs |
| HIP | ⚠️ broken VS2026+ | ✅ | ❌ | AMD GPUs on Linux |
| Vulkan | ✅ | ✅ | ✅ | AMD Windows, cross-platform |
| Metal | ❌ | ❌ | ✅ | Apple Silicon |

For AMD GPUs on **Windows**, Vulkan is the only reliably working backend and performs identically to HIP.

---

## Quick Reference: One-command builds

```bash
# NVIDIA CUDA
cmake -B build -DGGML_CUDA=ON && cmake --build build -j

# AMD Windows (Vulkan)
cmake -B build -DGGML_VULKAN=ON && cmake --build build -j

# AMD Linux (HIP)
cmake -B build -DGGML_HIP=ON -DCMAKE_CXX_COMPILER=hipcc -DGPU_TARGETS="gfx1100" && cmake --build build -j

# Apple Metal
cmake -B build -DGGML_METAL=ON && cmake --build build -j

# CPU only (fastest build, uses AVX2)
cmake -B build && cmake --build build -j
```
