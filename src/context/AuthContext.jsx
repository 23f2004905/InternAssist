import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

const AuthContext = createContext(null);

const API_URL = "http://localhost:5000/api";


export function AuthProvider({ children }) {

  const [currentUser, setCurrentUser] = useState(null);

  const [loading, setLoading] = useState(true);


  // --------------------------------
  // Check existing session
  // --------------------------------

  useEffect(() => {

    async function checkSession() {

      try {

        const response = await fetch(
          `${API_URL}/auth/me`,
          {
            credentials: "include",
          }
        );

        if (response.ok) {

          const data = await response.json();

          setCurrentUser(data.user);

        } else {

          setCurrentUser(null);

        }

      } catch (error) {

        console.error(
          "Session check failed:",
          error
        );

        setCurrentUser(null);

      } finally {

        setLoading(false);

      }
    }

    checkSession();

  }, []);


  // --------------------------------
  // Login
  // --------------------------------

  async function login(email, password) {

    try {

      const response = await fetch(
        `${API_URL}/auth/login`,
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          credentials: "include",

          body: JSON.stringify({
            email,
            password,
          }),
        }
      );


      const data = await response.json();


      if (!response.ok) {

        return {
          ok: false,
          error:
            data.error ||
            "Login failed.",
        };

      }


      setCurrentUser(data.user);


      return {
        ok: true,
        user: data.user,
      };


    } catch (error) {

      console.error(error);

      return {
        ok: false,
        error:
          "Unable to connect to the server.",
      };

    }
  }


  // --------------------------------
  // Register
  // --------------------------------

  async function register(form) {

    try {

      const response = await fetch(
        `${API_URL}/auth/register`,
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          credentials: "include",

          body: JSON.stringify({
            name: form.name,
            email: form.email,
            password: form.password,
            role: form.role,
          }),
        }
      );


      const data = await response.json();


      if (!response.ok) {

        return {
          ok: false,
          error:
            data.error ||
            "Registration failed.",
        };

      }


      return {
        ok: true,
        user: data.user,
      };


    } catch (error) {

      console.error(error);

      return {
        ok: false,
        error:
          "Unable to connect to the server.",
      };

    }
  }


  // --------------------------------
  // Logout
  // --------------------------------

  async function logout() {

    try {

      await fetch(
        `${API_URL}/auth/logout`,
        {
          method: "POST",
          credentials: "include",
        }
      );

    } catch (error) {

      console.error(
        "Logout error:",
        error
      );

    }

    setCurrentUser(null);
  }


  return (
    <AuthContext.Provider
      value={{
        currentUser,
        loading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}


export function useAuth() {

  const context = useContext(AuthContext);

  if (!context) {

    throw new Error(
      "useAuth must be used inside AuthProvider"
    );

  }

  return context;
}