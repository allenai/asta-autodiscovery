module.exports = {
    extends: ['@allenai/eslint-config-varnish'],
    rules: {
        'react/no-unescaped-entities': 'off',
        'no-undef': 'off', // TypeScript handles this
    },
};
