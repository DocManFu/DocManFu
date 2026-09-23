import { defineConfig, presetUno, presetIcons, transformerDirectives } from 'unocss';

const brand = {
	50: '#eef5ff',
	100: '#dbeafe',
	200: '#bcd7fd',
	300: '#8ec0fb',
	400: '#58a0f5',
	500: '#2f86ee',
	600: '#1a73e8',
	700: '#1463d6',
	800: '#1450a8',
	900: '#163f80',
	950: '#0f2a57'
};

// Cool slate grays matching docmanfu.com (paper #f4f7fb → ink #0b1220)
const gray = {
	50: '#f4f7fb',
	100: '#e6ecf4',
	200: '#d6dee9',
	300: '#b8c4d4',
	400: '#8391a6',
	500: '#5d6b80',
	600: '#4b5a70',
	700: '#2a3648',
	800: '#1e2a3d',
	900: '#131c2c',
	950: '#0b1220'
};

export default defineConfig({
	presets: [
		presetUno({ dark: 'class' }),
		presetIcons({
			scale: 1.2,
			extraProperties: {
				display: 'inline-block',
				'vertical-align': 'middle'
			}
		})
	],
	transformers: [transformerDirectives()],
	theme: {
		colors: {
			brand,
			blue: brand,
			gray
		}
	},
	shortcuts: {
		'btn': 'appearance-none px-4 py-2 rounded-lg font-medium transition-colors duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed',
		'btn-primary': 'btn bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800',
		'btn-secondary': 'btn bg-gray-100 text-gray-700 hover:bg-gray-200 active:bg-gray-300 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600 dark:active:bg-gray-500',
		'btn-danger': 'btn bg-red-50 text-red-700 hover:bg-red-100 active:bg-red-200 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50',
		'btn-ghost': 'btn text-gray-600 hover:bg-gray-100 active:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-700 dark:active:bg-gray-600',
		'btn-sm': 'px-3 py-1.5 text-sm',
		'btn-icon': 'p-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors cursor-pointer dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-200',
		'card': 'bg-white rounded-xl border border-gray-200 shadow-sm dark:bg-gray-800 dark:border-gray-700',
		'input-base': 'w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition-colors bg-white text-gray-900 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-100 dark:placeholder-gray-400',
		'badge': 'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
		'page-container': 'max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6'
	}
});
