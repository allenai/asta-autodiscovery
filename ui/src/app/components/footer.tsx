import styles from './footer.module.css';
import shared from '../shared.module.css';

export default function Footer() {
  return (
    <footer className={`${shared.centered} ${styles.footer}`}>
      <a href="https://allenai.org">© The Allen Institute for Artificial Intelligence</a> — All Rights Reserved
      {" "}| <a href="https://allenai.org/privacy-policy">Privacy Policy</a>
      {" "}| <a href="https://allenai.org/terms">Terms of Use</a>
      {" "}| <a href="https://allenai.org/business-code-of-conduct">Business Code of Conduct</a>
    </footer>
  );
}
