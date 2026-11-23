import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./Home.css";

const FEATURES = [
  {
    title: "Answers from your documents",
    text: "Ask in plain language. InternAssist searches the policies, circulars and guidelines your institution has uploaded and answers from them.",
  },
  {
    title: "Source citations",
    text: "Document-based answers list the document and page they were drawn from, so you can check the original yourself.",
  },
  {
    title: "Conversation history",
    text: "Your questions and answers are saved to your account, so you can return to earlier conversations after logging in again.",
  },
  {
    title: "Role-based access",
    text: "Students, faculty and administrators each get access to the features that fit their role.",
  },
];

const STEPS = [
  {
    title: "Administrators upload documents",
    text: "Internship policies, placement guidelines, regulations, notices and FAQs in PDF, DOCX, PPTX or TXT format.",
  },
  {
    title: "Documents are indexed",
    text: "The text is extracted, split into passages and prepared for search by meaning, not just keywords.",
  },
  {
    title: "You ask, it answers",
    text: "Get a clear answer with the sources it came from. The assistant is designed to say so when the documents do not cover a question.",
  },
];

const ROLES = [
  {
    title: "Students",
    text: "Ask questions about internships, placements and academic rules, and revisit your past conversations.",
  },
  {
    title: "Faculty",
    text: "Use the assistant and the institutional documents, and review your own conversations.",
  },
  {
    title: "Administrators",
    text: "Upload and manage documents, manage user accounts and look after the institutional knowledge base.",
  },
];

export default function Home() {
  const { currentUser, loading } = useAuth();

  let actions = null;

  if (!loading) {
    actions = currentUser ? (
      <Link to="/dashboard" className="btn-primary home-btn">
        Go to dashboard
      </Link>
    ) : (
      <>
        <Link to="/login" className="btn-secondary home-btn">
          Log in
        </Link>
        <Link to="/register" className="btn-primary home-btn">
          Register
        </Link>
      </>
    );
  }

  return (
    <div className="home-page">
      <div className="home-container">
        <header className="home-nav">
          <div className="home-brand">
            <div className="home-mark">IA</div>
            <span className="home-brand-name">InternAssist</span>
          </div>

          <div className="home-actions">{actions}</div>
        </header>

        <main>
          <section className="home-hero" aria-labelledby="home-title">
            <div>
              <p className="home-eyebrow">Institutional Q&amp;A Assistant</p>

              <h1 id="home-title" className="home-title">
                Answers from your institution&apos;s own documents.
              </h1>

              <p className="home-lead">
                Ask about internship policies, placement guidelines, academic
                regulations and notices in plain language, and get an answer
                with the source documents and pages it came from.
              </p>

              <div className="home-actions">{actions}</div>
            </div>

            <div className="home-demo card" aria-label="Example conversation">
              <div className="home-demo-head">
                <span className="badge badge-neutral">Example</span>
              </div>

              <p className="home-demo-q">
                How many parameters does the company supervisor evaluate?
              </p>

              <p className="home-demo-a">
                The company supervisor rates the intern on 17 parameters using
                a 5-point scale, from Excellent (5) to Poor (1).
              </p>

              <div className="home-demo-sources">
                <span className="home-demo-label">Sources</span>
                <span className="home-chip">Internship Logbook · PDF page 35</span>
              </div>
            </div>
          </section>

          <section className="home-section" aria-labelledby="home-features">
            <div className="home-section-head">
              <h2 id="home-features">What InternAssist does</h2>
              <p>
                One place for students and staff to find accurate answers
                without repeatedly asking the administration.
              </p>
            </div>

            <div className="home-grid-2">
              {FEATURES.map((item, index) => (
                <article key={item.title} className="home-card card">
                  <span className="home-card-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="home-section" aria-labelledby="home-how">
            <div className="home-section-head">
              <h2 id="home-how">How it works</h2>
            </div>

            <div className="home-grid-3">
              {STEPS.map((item, index) => (
                <article key={item.title} className="home-card card">
                  <span className="home-step">{index + 1}</span>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="home-section" aria-labelledby="home-roles">
            <div className="home-section-head">
              <h2 id="home-roles">Built for everyone involved</h2>
            </div>

            <div className="home-grid-3">
              {ROLES.map((item) => (
                <article key={item.title} className="home-card card">
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="home-cta" aria-labelledby="home-cta-title">
            <h2 id="home-cta-title">
              {currentUser ? "Welcome back" : "Ready to ask your first question?"}
            </h2>
            <p>
              {currentUser
                ? "Pick up where you left off."
                : "Create an account or log in to get started."}
            </p>
            <div className="home-actions home-actions-center">{actions}</div>
          </section>
        </main>

        <footer className="home-footer">
          InternAssist · Institutional Q&amp;A Assistant
        </footer>
      </div>
    </div>
  );
}