import time
import numpy as np

from gymnasium.wrappers import TimeLimit

from rl_task.rl_task_gym_wrapper import MouseTaskToGymWrapper


def init_keyboard(win_size=(640, 480)):
    import pygame

    pygame.init()
    win = pygame.display.set_mode(win_size)
    pygame.display.set_caption("Manual control (↑↓ move, ←→ turn, ESC quit)")
    return pygame, win


def get_action_from_keys(pygame, move_gain=1.0, turn_gain=1.0):
    keys = pygame.key.get_pressed()
    move = float(keys[pygame.K_UP] or keys[pygame.K_w]) - float(
        keys[pygame.K_DOWN] or keys[pygame.K_s]
    )
    turn = float(keys[pygame.K_RIGHT] or keys[pygame.K_d]) - float(
        keys[pygame.K_LEFT] or keys[pygame.K_a]
    )
    if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
        move_gain *= 0.5
        turn_gain *= 0.5
    move = np.clip(move * move_gain, -1.0, 1.0)
    turn = np.clip(turn * turn_gain, -1.0, 1.0)
    return np.array([move, turn], dtype=np.float32)


# -------------------- Obs → Surface helpers --------------------
def _first_image_like(obs):
    """Pick the first image-like numpy array from obs (supports array/list/tuple/dict)."""
    if isinstance(obs, np.ndarray) and obs.ndim in (2, 3, 4):
        return obs
    if isinstance(obs, (list, tuple)):
        for x in obs:
            if isinstance(x, np.ndarray) and x.ndim in (2, 3, 4):
                return x
    if isinstance(obs, dict):
        # try common keys first
        for k in ("visual", "image", "rgb", "obs", "camera"):
            if k in obs and isinstance(obs[k], np.ndarray) and obs[k].ndim in (2, 3, 4):
                return obs[k]
        for v in obs.values():
            if isinstance(v, np.ndarray) and v.ndim in (2, 3, 4):
                return v
    return None


def _to_rgb_uint8(img: np.ndarray) -> np.ndarray:
    """Convert array to HxWx3 uint8. Handles CHW/HWC, grayscale, alpha, batch size 1."""
    arr = img
    # Remove batch dim if present
    if arr.ndim == 4 and arr.shape[0] == 1:
        arr = arr[0]

    # CHW -> HWC (if channels first and channels <=4)
    if arr.ndim == 3 and arr.shape[0] in (1, 3, 4) and arr.shape[0] < arr.shape[-1]:
        arr = np.moveaxis(arr, 0, -1)

    # Grayscale -> RGB
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.ndim == 3 and arr.shape[-1] == 1:
        arr = np.repeat(arr, 3, axis=-1)

    # Drop alpha channel if present
    if arr.ndim == 3 and arr.shape[-1] == 4:
        arr = arr[..., :3]

    # To uint8
    if arr.dtype != np.uint8:
        mn, mx = float(arr.min()), float(arr.max())
        if 0.0 <= mn and mx <= 1.0:
            arr = (arr * 255.0).astype(np.uint8)
        else:
            rng = (mx - mn) or 1.0
            arr = ((arr - mn) / rng * 255.0).astype(np.uint8)
    return arr


def _center_crop_rgb(rgb: np.ndarray, size: int = 224) -> np.ndarray:
    """Center-crop to size x size. If the image is smaller, pad with black."""
    h, w, _ = rgb.shape
    ch, cw = min(size, h), min(size, w)
    y0 = (h - ch) // 2
    x0 = (w - cw) // 2
    cropped = rgb[y0 : y0 + ch, x0 : x0 + cw]

    # Pad to exact size if needed (when original < 224 on some axis)
    pad_h = size - ch
    pad_w = size - cw
    if pad_h > 0 or pad_w > 0:
        top = pad_h // 2
        bottom = pad_h - top
        left = pad_w // 2
        right = pad_w - left
        cropped = np.pad(
            cropped,
            ((top, bottom), (left, right), (0, 0)),
            mode="constant",
            constant_values=0,
        )
    return cropped


def obs_to_surface(pygame, win, obs, _cache={}):
    """Convert obs to a pygame.Surface scaled to window size; returns None if no image."""
    img = _first_image_like(obs)
    if img is None:
        return None
    rgb = _to_rgb_uint8(img)

    # rgb = _center_crop_rgb(rgb, 224)
    ih, iw = rgb.shape[0], rgb.shape[1]

    # cache base surface by image size
    key = (ih, iw)
    surf = _cache.get(key)
    if surf is None:
        surf = pygame.Surface((iw, ih))
        _cache[key] = surf

    # Fast blit (expects array shaped (W,H,3) -> transpose)
    pygame.surfarray.blit_array(surf, np.transpose(rgb, (1, 0, 2)))

    # Scale to window keeping aspect ratio
    win_w, win_h = win.get_size()
    scale = min(win_w / iw, win_h / ih)
    new_w, new_h = max(1, int(iw * scale)), max(1, int(ih * scale))
    if (new_w, new_h) != (iw, ih):
        surf = pygame.transform.smoothscale(surf, (new_w, new_h))
    return surf


def main():
    # Env
    env = MouseTaskToGymWrapper(
        # env_path="/Users/subnaulitus/Documents/EPFL/GitHub_Repos/FreelyMovingVR4Mice/rl_task/AR_build/macOS/augmented_reality.app",
        env_path=None,
        fps=60,
        base_port=5004,
        worker_id=0,
        batchmode=True,
        pos_reward_size=2.0,
        neg_reward_size=3.0,
        step_penalty_size=0.1,
    )
    env = TimeLimit(env, max_episode_steps=400)

    obs, info = env.reset(seed=42)

    # Initialize window (resize to first obs if available)
    default_win = (640, 480)
    pygame, win = init_keyboard(default_win)
    first_surf = obs_to_surface(pygame, win, obs)
    if first_surf is not None:
        # Resize window once to match obs aspect for nicer viewing
        pygame.display.set_mode(
            (max(320, first_surf.get_width()), max(240, first_surf.get_height()))
        )

    running = True
    steps_done = 0
    t0 = time.perf_counter()
    ema_fps, ema_alpha = None, 0.1

    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            action = get_action_from_keys(pygame, 1.0, 1.0)
            obs, _, terminated, truncated, info = env.step(action)
            steps_done += 1

            # Render visual observation
            surf = obs_to_surface(pygame, pygame.display.get_surface(), obs)
            if surf is not None:
                win = pygame.display.get_surface()
                win.fill((0, 0, 0))
                x = (win.get_width() - surf.get_width()) // 2
                y = (win.get_height() - surf.get_height()) // 2
                win.blit(surf, (x, y))
                pygame.display.flip()

            if terminated or truncated:
                obs, info = env.reset()
                print(f"[INFO] Episode length : {info['episode']['l']}")
                print(f"[INFO] Episode reward : {info['episode']['r']}")

            # FPS tracking
            now = time.perf_counter()
            dt = now - t0
            t0 = now
            inst_fps = (1.0 / dt) if dt > 0 else 0.0
            ema_fps = (
                inst_fps
                if ema_fps is None
                else (1 - ema_alpha) * ema_fps + ema_alpha * inst_fps
            )

            # Print FPS rarely and set window title
            if steps_done % 200 == 0:
                print(f"[{steps_done}] FPS≈{ema_fps:7.2f}")
                pygame.display.set_caption(
                    f"FPS≈{ema_fps:0.1f} | ↑↓ move, ←→ turn, ESC quit"
                )

    finally:
        try:
            env.close()
        except Exception:
            pass
        try:
            import pygame

            pygame.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
