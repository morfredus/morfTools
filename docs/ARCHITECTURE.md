# Workspace architecture

The `morfTools` project owns the shared manifest and administration scripts. Project-specific scripts stay inside each component project. The shared tools perform only generic lifecycle operations and resolve the workspace root relative to their own directory.

The manifest contains canonical production project names, the default branch, and the SSH clone template. Production tools use canonical names unchanged.

The Windows deployment synchronization script is deliberately separate from generic administration commands. It copies each declared sandbox project into its canonical production directory with Robocopy while excluding `.git` and build/editor artefacts. It does not rename content or replace text: production-capable scripts derive their mode from the enclosing project directory name.
