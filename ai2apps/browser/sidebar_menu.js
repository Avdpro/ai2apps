// Native Firefox chrome UI; never exposed as an Agent or Mini-Entry API.
let sidebarSiteDataBusy = false;

function sidebarMenuText(key) {
  return sidebarStrings[key];
}

function sidebarCurrentSite() {
  const uri = topWindow.gBrowser?.selectedBrowser?.currentURI;
  if (!uri || !["http", "https"].includes(uri.scheme)) return null;
  return Services.eTLD.getSchemelessSite(uri);
}

async function clearSidebarSiteData(site) {
  if (sidebarSiteDataBusy || !site || site !== sidebarCurrentSite()) return;
  const confirmed = Services.prompt.confirm(
    window,
    sidebarMenuText("deleteData"),
    sidebarMenuText("deleteDataConfirm").replace("{domain}", site)
  );
  if (!confirmed) return;
  sidebarSiteDataBusy = true;
  try {
    const failedFlags = await new Promise(resolve => {
      Services.clearData.deleteDataFromSite(
        site, {}, true,
        Ci.nsIClearDataService.CLEAR_COOKIES_AND_SITE_DATA |
          Ci.nsIClearDataService.CLEAR_ALL_CACHES,
        resolve
      );
    });
    if (failedFlags) throw new Error("site_data_clear_failed");
    await refreshContext({ force: true });
    Services.prompt.alert(window, sidebarMenuText("deleteData"),
      sidebarMenuText("deleteDataSuccess").replace("{domain}", site));
  } catch (error) {
    console.error("AI2Apps site data clear failed", error);
    Services.prompt.alert(window, sidebarMenuText("deleteData"),
      sidebarMenuText("deleteDataFailed"));
  } finally {
    sidebarSiteDataBusy = false;
  }
}

function openSidebarActions(event) {
  const button = document.getElementById("refresh-context");
  let menu = document.getElementById("sidebar-actions-menu");
  if (!menu) {
    menu = document.createXULElement("menupopup");
    menu.id = "sidebar-actions-menu";
    const refresh = document.createXULElement("menuitem");
    refresh.id = "sidebar-action-refresh";
    refresh.addEventListener("command", () => refreshContext({ force: true }));
    const clear = document.createXULElement("menuitem");
    clear.id = "sidebar-action-clear-data";
    clear.addEventListener("command", () => clearSidebarSiteData(clear.dataset.site));
    menu.append(refresh, clear);
    document.documentElement.append(menu);
  }
  const site = sidebarCurrentSite();
  menu.children[0].setAttribute("label", sidebarStrings.refresh);
  menu.children[1].setAttribute("label", site
    ? `${sidebarMenuText("deleteData")} (${site})…`
    : sidebarMenuText("deleteData"));
  menu.children[1].dataset.site = site || "";
  menu.children[1].disabled = !site || sidebarSiteDataBusy;
  menu.openPopup(button, "after_end", 0, 0, false, false, event);
}
