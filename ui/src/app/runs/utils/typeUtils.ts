export function isNumber(any: any): any is number {
    return typeof any === 'number';
}

export function isString(any: any): any is string {
    return typeof any === 'string';
}

export function isBoolean(any: any): any is boolean {
    return typeof any === 'boolean';
}

export function isFunction<T = (...args: any[]) => any>(any: any): any is T {
    return typeof any === 'function';
}

export function isObject<T = object>(any: any): any is T {
    return any !== null && typeof any === 'object';
}

// Determines if value is a plain object (vs a class or other primitive)
export function isPojo<T = Record<string, any>>(any: any): any is T {
    return isObject(any) && Object.getPrototypeOf(any) === Object.prototype;
}

export function isBigInt(any: any): any is bigint {
    return typeof any === 'bigint';
}

export function isSymbol(any: any): any is symbol {
    return typeof any === 'symbol';
}

export function isRegExp(any: any): any is RegExp {
    return any instanceof RegExp;
}

export function isUndefined(any: any): any is undefined {
    return typeof any === 'undefined';
}

export function isNull(any: any): any is null {
    return any === null;
}

export function hasValue<T>(any: T | undefined | null): any is Exclude<T, null | undefined> {
    const isNonValue = isNull(any) || isUndefined(any);
    return !isNonValue;
}

export function isArray<T>(any: any): any is T[] {
    return Array.isArray(any);
}
