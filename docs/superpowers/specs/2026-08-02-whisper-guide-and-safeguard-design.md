# Design Specification: Whisper.cpp Build Guide & 3-Hour Benchmark Safeguard

**Date**: 2026-08-02  
**Status**: Approved  

---

## 1. Overview
This document specifies the updated build guide for `whisper.cpp` across Windows, Linux, and macOS platforms, as well as the **3-Hour Benchmark Pre-check Safeguard** designed to prevent long, slow transcriptions on underpowered PC hardware.

---

## 2. Pre-Flight Benchmark Safeguard (3-Hour Rule)

### 2.1 Concept
Before initiating a full video transcription, a 10-second sample benchmark is executed.

### 2.2 Calculation Formula
1. **Sample Speed Ratio ($R$)**:
   $$R = \frac{10\text{ seconds}}{T_{\text{sample}}}$$
2. **Predicted Total Render Time ($T_{\text{predicted}}$)**:
   $$T_{\text{predicted}} = \frac{\text{Total Audio Duration}}{R}$$

### 2.3 Hard Gate Policy
- **Threshold**: 3 Hours (10,800 seconds).
- **If $T_{\text{predicted}} > 3\text{ hours}$**: Abort full rendering immediately. Return error:
  `[ERROR] Predicted transcription time (X.X hours) exceeds 3-hour limit on this hardware. Full rendering refused.`
- **If $T_{\text{predicted}} \le 3\text{ hours}$**: Proceed with full transcription.

---

## 3. Multi-Platform Build Instructions

### 3.1 Windows (MinGW GCC 15.2 - Verified Local Build)
```powershell
pip install cmake
git clone https://github.com/ggerganov/whisper.cpp.git C:\Users\SMTE-PC\whisper.cpp
cd C:\Users\SMTE-PC\whisper.cpp
cmake -B build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 8
```
- **Local Executable Path**: `C:\Users\SMTE-PC\whisper.cpp\build\bin\whisper-cli.exe`

### 3.2 Linux
- **CPU (AVX2)**:
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

### 3.3 macOS (Apple Silicon Metal)
```bash
cmake -B build -DGGML_METAL=ON && cmake --build build -j
```

---

## 4. Hardware Benchmarks & Performance Reference

### 4.1 Model Memory Requirements
| Model | Parameter Size | VRAM / RAM Required |
|---|---|---|
| `tiny` | 39 M | ~1 GB |
| `base` | 74 M | ~2 GB |
| `small` | 244 M | ~3 GB |
| `medium` | 769 M | ~5 GB |
| `large-v3-turbo` | 809 M | ~1.5 GB (fp16) |

### 4.2 Intel Core i3-12100 AVX2 Speed Table (`large-v3-turbo`)
| Stream Length | Speed Ratio | Render Time | 3-Hour Target |
|---|---|---|---|
| 1 Hour | 10x | ~6 mins | ✅ Pass |
| 3 Hours | 10x | ~18 mins | ✅ Pass |
| 6 Hours | 10x | ~36 mins | ✅ Pass |
| 10 Hours | 10x | ~60 mins | ✅ Pass |
| 18 Hours | 10x | ~108 mins | ✅ Pass |

---

## 5. File Targets
1. `BUILD_WHISPERCPP_GUILD.md` (Updated markdown document)
2. `skills/anibon-local-transcription/scripts/benchmark_check.py` (Script implementing pre-check safeguard)
