# Build & Benchmark Guide for whisper.cpp

Complete cross-platform compilation guide and hardware benchmark safeguard for `whisper.cpp`.

---

## 1 Pre-Flight Benchmark Safeguard (3-Hour Rule)

Before starting a full video transcription, run a **10-second sample pre-check** to estimate rendering speed.

### 1.1 Calculation Formula
1. **Speed Ratio ($R$)**:
   $$R = \frac{10\text{ seconds}}{T_{\text{sample}}}$$
2. **Predicted Total Render Time ($T_{\text{predicted}}$)**:
   $$T_{\text{predicted}} = \frac{\text{Total Audio Duration}}{R}$$

### 1.2 Safeguard Policy
- **Threshold Limit**: **3 Hours** (10,800 seconds).
- **If $T_{\text{predicted}} > 3\text{ hours}$**: **REFUSE** full render. Abort immediately with error:
  `[ERROR] Predicted transcription time (X.X hours) exceeds 3-hour limit on this PC hardware. Aborting.`
- **If $T_{\text{predicted}} \le 3\text{ hours}$**: Safe to proceed with full transcription.

---

## 2 Multi-Platform Build Instructions

### 2.1 Windows (MinGW GCC 15.2 - Verified Local Build)
Recommended setup for Windows without Visual Studio overhead:

```powershell
# 1. Install CMake via pip
pip install cmake

# 2. Clone whisper.cpp repository
git clone https://github.com/ggerganov/whisper.cpp.git C:\Users\SMTE-PC\whisper.cpp
cd C:\Users\SMTE-PC\whisper.cpp

# 3. Configure & Compile (8 threads, AVX2)
$env:PATH += ";C:\Users\SMTE-PC\AppData\Roaming\Python\Python314\Scripts;C:\ProgramData\mingw64\mingw64\bin"
cmake -B build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 8
```

- **Compiled Binary Path**: `C:\Users\SMTE-PC\whisper.cpp\build\bin\whisper-cli.exe`

---

### 2.2 Linux
Supported backends: CUDA, HIP (ROCm), CPU (AVX2).

- **CPU Only (AVX2)**:
  ```bash
  cmake -B build && cmake --build build -j
  ```
- **NVIDIA CUDA**:
  ```bash
  cmake -B build -DGGML_CUDA=ON && cmake --build build -j
  ```
- **AMD ROCm / HIP**:
  ```bash
  cmake -B build -DGGML_HIP=ON -DCMAKE_CXX_COMPILER=hipcc -DGPU_TARGETS="gfx1100" && cmake --build build -j
  ```

---

### 2.3 macOS (Apple Silicon Metal)
Supported on M1/M2/M3/M4 Apple Silicon.

```bash
cmake -B build -DGGML_METAL=ON && cmake --build build -j
```

---

## 3 Model Selection & Hardware Benchmarks

### 3.1 Model VRAM / RAM Requirements
| Model | Size | Parameter Count | VRAM / RAM (fp16) |
|---|---|---|---|
| `tiny` | 75 MB | 39 M | ~1 GB |
| `base` | 150 MB | 74 M | ~2 GB |
| `small` | 500 MB | 244 M | ~3 GB |
| `medium` | 1.5 GB | 769 M | ~5 GB |
| `large-v3-turbo` | 1.5 GB | 809 M | ~1.5 GB |

---

### 3.2 Intel Core i3-12100 AVX2 Speed Benchmark
Hardware Specs: **4 Cores / 8 Threads** with `AVX2` + `AVX_VNNI` + `FMA` + `OpenMP`.  
Model: `ggml-large-v3-turbo.bin`

| Stream / Audio Duration | Real-Time Speed Ratio | Actual Processing Time | 3-Hour Limit Check |
|---|---|---|---|
| **1 Hour** | **10x speed** (0.10 RTF) | **~6 minutes** | ✅ Pass |
| **3 Hours** | **10x speed** (0.10 RTF) | **~18 minutes** | ✅ Pass |
| **6 Hours** | **10x speed** (0.10 RTF) | **~36 minutes** | ✅ Pass |
| **10 Hours** | **10x speed** (0.10 RTF) | **~60 minutes (1 hr)** | ✅ Pass |
| **18 Hours** | **10x speed** (0.10 RTF) | **~108 minutes (1.8 hrs)** | ✅ Pass |

---

## 4 Hardware Diagnostic Verification

Run `whisper-bench.exe` to inspect hardware acceleration flags on your system:

```powershell
C:\Users\SMTE-PC\whisper.cpp\build\bin\whisper-bench.exe -t 8
```

Look for active CPU hardware flags in the output:
```
system_info: n_threads = 8 / 8 | CPU : SSE3 = 1 | SSSE3 = 1 | AVX = 1 | AVX_VNNI = 1 | AVX2 = 1 | F16C = 1 | FMA = 1 | BMI2 = 1 | OPENMP = 1
```
