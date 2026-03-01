const DEFAULT_AUTH_WINDOW_MS = 4000;

let authorizedDepth = 0;
let authorizedUntil = 0;

const now = () => Date.now();

const isAuthorized = () => authorizedDepth > 0 || now() <= authorizedUntil;

const createUnauthorizedError = methodName => {
    const error = new Error(`[Security] Blocked unauthorized VM export call: ${methodName}`);
    error.name = 'UnauthorizedProjectExportError';
    return error;
};

const withProjectExportAuthorization = callback => {
    authorizedDepth += 1;
    try {
        return callback();
    } finally {
        authorizedDepth -= 1;
    }
};

const authorizeProjectExportFor = (durationMs = DEFAULT_AUTH_WINDOW_MS) => {
    authorizedUntil = Math.max(authorizedUntil, now() + durationMs);
};

const guardMethod = (vm, methodName) => {
    if (typeof vm[methodName] !== 'function') return;

    const originalMethod = vm[methodName].bind(vm);
    vm[methodName] = (...args) => {
        if (!isAuthorized()) {
            throw createUnauthorizedError(methodName);
        }
        return originalMethod(...args);
    };
};

const guardVMExportMethods = vm => {
    if (!vm || vm.__twExportGuardApplied) {
        return vm;
    }

    guardMethod(vm, 'saveProjectSb3');
    guardMethod(vm, 'saveProjectSb3Stream');
    guardMethod(vm, 'exportSprite');

    Object.defineProperty(vm, '__twExportGuardApplied', {
        value: true,
        enumerable: false,
        configurable: false,
        writable: false
    });

    return vm;
};

export {
    authorizeProjectExportFor,
    guardVMExportMethods,
    withProjectExportAuthorization
};
