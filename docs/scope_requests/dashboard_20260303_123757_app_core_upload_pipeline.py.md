```diff
diff --git a/app/core/upload_pipeline.py b/app/core/upload_pipeline.py
index c928aea..9d85fa7 100644
--- a/app/core/upload_pipeline.py
+++ b/app/core/upload_pipeline.py
@@ -118,8 +118,6 @@ def _scan_malware(file_path: Path) -> Tuple[bool, str]:
 
         cd = pyclamd.ClamdUnixSocket()
         if not cd.ping():
-            if os.environ.get("CLAMAV_OPTIONAL") == "1":
-                return True, "CLAMAV_UNAVAILABLE"
             return False, "CLAMAV_UNAVAILABLE"
         result = cd.scan_file(str(file_path))
         if result:
@@ -127,8 +125,6 @@ def _scan_malware(file_path: Path) -> Tuple[bool, str]:
             return False, "INFECTED"
         return True, "CLEAN"
     except Exception:
-        if os.environ.get("CLAMAV_OPTIONAL") == "1":
-            return True, "CLAMAV_UNAVAILABLE"
         return False, "CLAMAV_UNAVAILABLE"
 
 
```
