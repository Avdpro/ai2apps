# Shared AceFox Bundle

AI2Apps packages one immutable Gecko/AceFox bundle at
`Contents/Applications/AI2AppsShell.app`. The desktop Shell and every
actor-bound Web Agent launch separate processes from this same bundle.

## Runtime separation

- The App Shell uses the private `app-shell` profile.
- Each Web Agent uses a profile derived from its Installation and actor.
- Every Agent receives a unique BiDi port, authentication token, process
  lease, download directory, and browser profile.
- Agent processes set `AI2APPS_BROWSER_ROLE=agent` and `MOZ_APP_NO_DOCK=1`.
  AceFox therefore skips signed App-Shell argument injection and keeps the
  visible Agent window out of the Dock and Command-Tab switcher.

Program files are shared; mutable profiles, sessions, permissions, and process
lifecycle are not.

## Packaging and trust boundary

The Helper resolves AceFox only from the containing signed App at
`Contents/Applications/AI2AppsShell.app/Contents/MacOS/acefox-bin`. It rejects
arbitrary executable overrides in packaged mode and requires the signed
`AI2AppsSharedBrowserBundle` contract in the Shell Info.plist.

Release verification rejects the retired duplicated
`Helper/Contents/Resources/AceFoxAgent.app`, checks that the shared browser
contract is present, and verifies the AceFox binary contains shared Agent-role
support before signing and publication.

## Size result

The development acceptance build decreased from 782 MB to 392 MB while two
independent Agent profiles simultaneously completed authenticated WebDriver
BiDi sessions from the single shared bundle.
