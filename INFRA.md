# G Cloud Bucket

 Modal GCS CloudBucketMount expects a secret with keys named GOOGLE_ACCESS_KEY_ID and GOOGLE_ACCESS_KEY_SECRET

 It can be created with:

 ```sh
 modal secret create gcs-autodiscovery \
    GOOGLE_ACCESS_KEY_ID=... \
    GOOGLE_ACCESS_KEY_SECRET=...
```
