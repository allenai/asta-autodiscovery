import styles from './header.module.css';
import shared from '../shared.module.css';
import Image from 'next/image'

const ratio = 177/20;
const height = 20;

export default function Home() {
  return (
    <header className={styles.header}>
      <div className={`${shared.centered} ${styles['header-content']}`}>
        <a href="https://allenai.org">
          <Image
            width={height*ratio}
            height={height}
            src="/ai2-logo-horizontal-lockup-white.svg"
            alt="The Allen Institute for Artificial Intelligence Logo" />
        </a>
      </div>
    </header>
  );
}
