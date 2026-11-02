package com.scf.config;

import com.scf.domain.DrawdownService;

public final class AppContext {
    public static final DrawdownService SERVICE = new DrawdownService();
    private AppContext() {}
}
