# environment.py
"""
EnvironmentManager - Initializes Vizard and loads the required gallery scene.
RECTIFIED v4.0: Gallery loading is mandatory; raises RuntimeError if unavailable.
"""

import os

try:
    import viz
    import vizshape
except Exception:
    viz = vizshape = None


class EnvironmentManager:
    def __init__(self):
        self.gallery = None
        self._started = False

    def setup_viz_engine(self, fullscreen=False, gallery_path='gallery.osgb'):
        """
        Initialize Vizard engine and load the gallery scene (REQUIRED).

        Args:
            fullscreen (bool): Whether to run fullscreen.
            gallery_path (str): Filename or path to gallery.osgb (required).

        Raises:
            RuntimeError: If viz not available or gallery cannot be loaded.
        """
        if viz is None:
            raise RuntimeError("Vizard (viz) not available. Install/enable Vizard in your Python environment.")

        print("[ENVIRONMENT] Initializing Vizard engine...")

        # Try a few renderer settings (best-effort)
        try:
            viz.setMultiSample(4)
        except Exception:
            pass
        try:
            viz.fov(60)
        except Exception:
            pass

        # Start Vizard
        try:
            if fullscreen:
                viz.go(viz.FULLSCREEN)
            else:
                viz.go()
        except Exception as e:
            print(f"[ENVIRONMENT] Error starting Vizard: {e}")
            try:
                viz.go()
            except Exception:
                raise RuntimeError("Failed to start Vizard graphics engine.")

        # Basic camera defaults
        try:
            viz.MainView.setPosition([0, 1.25, -1.1])
            viz.MainView.lookAt([0, 1.0, 2.5])
        except Exception:
            pass

        # Disable default headlight if present
        try:
            head = viz.MainView.getHeadLight()
            try:
                head.disable()
            except Exception:
                pass
        except Exception:
            pass

        # Add consistent lighting so gallery + hand are visible
        try:
            amb = viz.addLight()
            try:
                amb.ambient([0.6, 0.6, 0.6])
            except Exception:
                pass
            try:
                amb.diffuse([0.5, 0.5, 0.5])
            except Exception:
                pass
        except Exception:
            pass

        try:
            sun = viz.addDirectionalLight(euler=(45, 45, 0))
            try:
                sun.diffuse([1.0, 0.98, 0.95])
            except Exception:
                try:
                    sun.color([1.0, 0.98, 0.95])
                except Exception:
                    pass
            try:
                sun.ambient([0.2, 0.2, 0.2])
            except Exception:
                pass
        except Exception:
            pass

        # Load gallery model (MANDATORY)
        print(f"[ENVIRONMENT] Loading required gallery scene from: {gallery_path}")
        gallery_node = None
        try:
            if os.path.isabs(gallery_path):
                if not os.path.exists(gallery_path):
                    raise RuntimeError(f"Gallery file not found at absolute path: {gallery_path}")
                gallery_node = viz.addChild(gallery_path)
            else:
                if os.path.exists(gallery_path):
                    gallery_node = viz.addChild(gallery_path)
                else:
                    gallery_node = viz.addChild(gallery_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load gallery.osgb ('{gallery_path}'): {e}\nPlace gallery.osgb in the application folder or set the correct path.")

        if not gallery_node:
            raise RuntimeError(f"viz.addChild returned None for '{gallery_path}'. Ensure the file is a valid OSGB and readable.")

        self.gallery = gallery_node
        try:
            self.gallery.visible(True)
        except Exception:
            pass

        try:
            viz.clearcolor(0.12, 0.12, 0.15)
        except Exception:
            pass

        print("[ENVIRONMENT] ✓ Gallery loaded successfully and environment initialized.")
        self._started = True
        return True

    def get_gallery(self):
        """Return the loaded gallery node (guaranteed after successful setup)."""
        return self.gallery

    def is_ready(self):
        """Return whether environment has been initialized."""
        return self._started