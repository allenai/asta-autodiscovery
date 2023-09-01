import styles from './main.module.css';
import shared from '../shared.module.css';

export default function Main({ children }: { children: React.ReactNode }) {
  return <main className={`${shared.centered} ${styles.main}`}>{children}</main>;
}
