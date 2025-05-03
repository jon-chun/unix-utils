**Troubleshooting GPU issues**

It sounds like after switching to Debian and updating, the NVIDIA drivers might have been upgraded, causing Ollama to stop using the GPU. Apt upgrade could have updated the NVIDIA drivers, leading to mismatches with CUDA. The simplest solution might be to reboot, which would reload the kernel modules properly. You can check the status with nvidia-smi or systemctl status nvidia-hydra. Just make sure the OLLAMA\_USE\_GPU environment variable is set when restarting Ollama with the GPU flag.

**Providing troubleshooting steps**

To fix this GPU issue, follow these steps:

1. Quick checks: reboot, ensure driver is loaded with `nvidia-smi`, and check Ollama logs for GPU usage.
2. Diagnostics:

   * Run `nvidia-smi` to check driver.
   * Use `cat /proc/driver/nvidia/version`.
   * Restart Ollama and monitor with `nvidia-smi`.
3. If necessary, set the `OLLAMA_ORCA_CUDA` variable, or reboot to reload drivers properly.

For future updates: Pin NVIDIA driver packages with `apt-mark hold` to prevent auto-updates and avoid mismatches.

**Future-proofing Docker & NVIDIA setup**

To protect your Ollama, Docker, and NVIDIA setup during future upgrades, consider using tools like `apt-mark` hold or an apt preference file to pin specific package versions. Using Ubuntu's 'Pro' stable updates or pinning Docker images can further stabilize things. It's also handy to pin GPU drivers from the graphics-driver PPA. Lastly, setting up a separate environment for development or using virtualization can add extra layers of security against disruptions.


**Protecting setup during upgrades**

For future upgrades, use tools like `apt-mark hold` or `apt preferences` to pin specific versions and avoid unwanted updates. Docker images can also be pinned for stability, and GPU drivers from the graphics-drivers PPA should be held. You may need `ubuntu-drivers devices` to manage drivers properly. Consider creating a separate development environment or using virtualization as added protection. As a quick recourse, consider restoring specific driver versions with `apt install` commands.


**Troubleshooting GPU usage**

It looks like the GPU might not be used due to a driver mismatch or not being loaded. This could be because a reboot is needed, or the nvidia-container-toolkit isn't integrated. To check:

1. Ensure the driver is loaded; run `nvidia-smi`. If it fails, reboot or reinstall the driver.
2. Check `/usr/bin/nvidia-ctk runtime list` and confirm environment variables like `NVIDIA_VISIBLE_DEVICES=all`.
3. Test with `ollama run llama3` and check `nvidia-smi`. If issues persist, check logs with `OLLAMA_DEBUG=1 ollama serve`.


**Upgrades Protection and GPU Setup**

It looks like the “could not load libcuda.so” error might happen if the path to `libcuda.so.1` is missing. First, confirm the existence of `/usr/lib/x86_64-linux-gnu/libcuda.so.1`. For Docker, make sure to mount NVIDIA libraries correctly. You should add your user to the Docker group and check Docker with `docker info`.

For upgrades: Consider using `apt-mark hold` to lock the NVIDIA driver or use package version control. You can also freeze the kernel to avoid mismatches, and back up with Timeshift. Virtualization could also help unify your setup.


Thought for 1m 17s


**Executive‑summary**

\* Your VS Code switch itself can’t disable Ollama’s CUDA path; what changed is that `apt upgrade` likely **installed a newer NVIDIA kernel‑module/userspace pair that isn’t active until a reboot**.
\* A single reboot (or at least a full `modprobe nvidia` cycle + Docker restart) normally restores GPU visibility.
\* To keep future `apt upgrade` runs from “surprising” you, pin the exact driver/kernel pair you know is stable and tell unattended‑upgrades to ignore them. The same trick works for Docker + nvidia‑container‑toolkit and for Ollama’s own package.

Below you’ll find:

1. a 2‑minute checklist to bring the GPU back right now,
2. verification commands,
3. safe‑upgrade playbook for the long run.

---

## 1  | Get the GPU back in three steps

| #     | Command                                                                | Why                                                                                                                                 |
| ----- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **1** | `nvidia-smi`                                                           | Fastest way to see if the kernel picked up the new module. If it errors, the module isn’t loaded.                                   |
| **2** | `sudo systemctl restart docker`   *(if you run Ollama in a container)* | Docker picks up the updated NVIDIA runtime only after a restart.                                                                    |
| **3** | `sudo reboot` *(recommended)*                                          | Guarantees the new kernel+driver pair is live and every service (Ollama, Docker, VS Code) is linked against the fresh `libcuda.so`. |

> 📝  Hot‑reload without reboot
>
> ```
> sudo modprobe -r nvidia_uvm nvidia_drm nvidia_modeset nvidia
> sudo modprobe nvidia
> sudo systemctl restart ollama   # or docker again
> ```
>
> …but on a desktop with X/Wayland running, unloading those modules is often blocked—reboot is safer.

---

## 2  | Confirm Ollama really sees CUDA

```bash
# Bare‑metal install:
ollama serve --debug 2>&1 | grep -i cuda

# Docker:
docker exec -it ollama nvidia-smi
docker logs ollama | grep -i "Dynamic LLM libraries"
```

A healthy log line looks like:

````
Dynamic LLM libraries [cuda_v11 rocm_v60002 cpu cpu_avx ...] 🟢
``` :contentReference[oaicite:0]{index=0}  

If you instead see *“CUDA disabled – falling back to CPU”* or nothing about `cuda_v11`, Ollama still can’t open `libcuda.so` → double‑check `nvidia-smi`, driver version, and that you didn’t upgrade to the **555 beta** driver (known to break Ollama) :contentReference[oaicite:1]{index=1}.

---

## 3  | Why upgrades sometimes break GPU apps

1. **Driver / kernel mismatch** – `apt upgrade` pulls in a newer NVIDIA userspace but the matching DKMS module isn’t compiled until the next boot.  
2. **nvidia‑container‑toolkit version skew** – Docker’s GPU runtime has to match the installed driver ABI.  
3. **CUDA minor version gating inside Ollama** – releases before *0.1.38* refused driver ≥ 555. :contentReference[oaicite:2]{index=2}  
4. **Kernel upgrades** – a new `linux-image-6.xx…` invalidates the currently compiled DKMS module.

---

## 4  | Long‑term hardening: freeze what matters

> The goal is *predictability*—you decide when to take a new driver, kernel, or Ollama build.

### 4.1  Pin the driver & kernel

```bash
# Find the exact versions you’re happy with
dpkg -l | grep nvidia-driver
uname -r

# Freeze them
sudo apt-mark hold nvidia-driver-535 nvidia-kernel-common-535 \
                   nvidia-kernel-source-535 nvidia-dkms-535 \
                   linux-image-generic linux-headers-generic
````

Later, to upgrade on your own terms:

```bash
sudo apt-mark unhold nvidia-driver-*  # upgrade, test, then hold again
```

### 4.2  Pin Docker’s GPU toolkit

```bash
sudo apt-mark hold nvidia-container-toolkit nvidia-container-runtime
```

### 4.3  Exclude in unattended‑upgrades

Edit `/etc/apt/apt.conf.d/50unattended-upgrades`:

```text
Package-Blacklist {
    "nvidia-driver-535";
    "nvidia-kernel-common-535";
    "linux-image-generic";
    "nvidia-container-toolkit";
    "ollama";
};
```

### 4.4  Snapshot before big jumps

* Use **Timeshift** or `btrfs` snapshots (desktop) or a VM/LXC clone (server) before unfreezing anything major.
* Keep a copy of the working driver in `/var/cache/apt/archives/` (`apt-get download nvidia-driver-535`).

---

## 5  | Upgrade playbook (copy‑paste for next time)

```bash
# 0. Create snapshot / timeshift
# 1. Unhold packages you want to test
sudo apt-mark unhold nvidia-driver-* nvidia-container-toolkit ollama

# 2. Simulate upgrade
apt-get -s dist-upgrade | less

# 3. Do the real upgrade
sudo apt-get dist-upgrade

# 4. Reboot and verify
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.4.1-base nvidia-smi
ollama run llama3:8b -p "hi" | head

# 5. If everything is fine, hold again
sudo apt-mark hold nvidia-driver-* nvidia-container-toolkit ollama
```

---

### ✅  What to remember

1. **Reboot after any driver or kernel change**—it’s the simplest fix for “CUDA vanished”.
2. **Pin driver + toolkit + kernel** to avoid accidental mismatches.
3. **Upgrade in a controlled window**, snapshot first, and you’ll keep your RTX 3090‑powered Ollama stack humming regardless of what Ubuntu’s next `apt upgrade` throws your way.

Feel free to let me know if any step still leaves the GPU idle—there are deeper diagnostics (like checking `/proc/driver/nvidia/version` or `ldd $(which ollama) | grep cuda`) we can run if needed. Happy (stable) hacking!
